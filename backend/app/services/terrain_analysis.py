"""
Terrain 3D analysis using Structure-from-Motion (SfM) principles.

Pipeline:
  1. Extract frames from video or accept individual images.
  2. Detect ORB keypoints and compute binary descriptors on each frame.
  3. Match consecutive frame pairs with BFMatcher (Hamming distance).
  4. Estimate the Essential Matrix via RANSAC and recover camera pose (R, t).
  5. Triangulate 3D points from inlier correspondences.
  6. Aggregate the sparse point cloud and compute terrain metrics:
       - estimated ground area (convex hull of XY projection)
       - slope (normal of best-fit plane)
       - elevation differential
       - surface regularity (residuals from best-fit plane)
       - terrain classification + foundation recommendation
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

try:
    from scipy.spatial import ConvexHull
    _SCIPY = True
except ImportError:
    _SCIPY = False


class TerrainAnalyzer:
    def __init__(self):
        self.orb = cv2.ORB_create(nfeatures=2000)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_from_paths(self, file_paths: List[str]) -> dict:
        """
        Entry point: accepts a list of absolute file paths (images or videos).
        Returns a metrics dict.
        """
        frames: List[np.ndarray] = []
        for path in file_paths:
            ext = Path(path).suffix.lower()
            if ext in {".mp4", ".mov", ".avi", ".webm", ".mkv", ".3gp"}:
                frames.extend(self._extract_frames(path, max_frames=40))
            else:
                img = cv2.imread(path)
                if img is not None:
                    frames.append(img)

        return self._analyze(frames)

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    def _extract_frames(self, video_path: str, max_frames: int = 40) -> List[np.ndarray]:
        frames: List[np.ndarray] = []
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return frames

        step = max(1, total // max_frames)
        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            if len(frames) >= max_frames:
                break

        cap.release()
        return frames

    # ------------------------------------------------------------------
    # Main analysis pipeline
    # ------------------------------------------------------------------

    def _analyze(self, frames: List[np.ndarray]) -> dict:
        if not frames:
            return self._empty_result(reason="No se recibieron frames")
        if len(frames) == 1:
            return self._single_frame_result(frames[0])

        # Resize large frames for speed while preserving aspect ratio
        frames = [self._resize(f) for f in frames]

        h, w = frames[0].shape[:2]
        # Approximate pinhole camera matrix (focal ≈ 0.9 * width)
        focal = 0.9 * w
        K = np.array(
            [[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], dtype=np.float64
        )

        all_kps, all_desc = [], []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kps, desc = self.orb.detectAndCompute(gray, None)
            all_kps.append(kps)
            all_desc.append(desc)

        points_3d: List[np.ndarray] = []

        for i in range(len(frames) - 1):
            if all_desc[i] is None or all_desc[i + 1] is None:
                continue

            matches = self.matcher.match(all_desc[i], all_desc[i + 1])
            matches = sorted(matches, key=lambda m: m.distance)[:300]
            if len(matches) < 8:
                continue

            pts1 = np.float32([all_kps[i][m.queryIdx].pt for m in matches])
            pts2 = np.float32([all_kps[i + 1][m.trainIdx].pt for m in matches])

            E, mask = cv2.findEssentialMat(
                pts1, pts2, K, method=cv2.RANSAC, prob=0.999, threshold=1.0
            )
            if E is None or mask is None:
                continue

            _, R, t, mask_pose = cv2.recoverPose(E, pts1, pts2, K, mask=mask)

            P1 = K @ np.hstack([np.eye(3), np.zeros((3, 1))])
            P2 = K @ np.hstack([R, t])

            inlier_mask = mask_pose.ravel() > 0
            p1_in = pts1[inlier_mask].T
            p2_in = pts2[inlier_mask].T

            if p1_in.shape[1] < 4:
                continue

            pts4d = cv2.triangulatePoints(P1, P2, p1_in, p2_in)
            w_coord = pts4d[3]
            valid_w = np.abs(w_coord) > 1e-6
            pts4d = pts4d[:, valid_w]
            w_coord = w_coord[valid_w]
            pts3 = (pts4d[:3] / w_coord).T

            # Remove statistical outliers
            dists = np.linalg.norm(pts3, axis=1)
            med, std = np.median(dists), np.std(dists)
            keep = np.abs(dists - med) < 3 * std
            points_3d.append(pts3[keep])

        if not points_3d:
            return self._empty_result(reason="No se pudieron triangular puntos 3D")

        cloud = np.vstack(points_3d)
        return self._compute_metrics(cloud, len(frames))

    # ------------------------------------------------------------------
    # Metric computation
    # ------------------------------------------------------------------

    def _compute_metrics(self, cloud: np.ndarray, n_frames: int) -> dict:
        n = len(cloud)
        scan_quality = min(100, n // 40)

        z = cloud[:, 2]
        z_lo, z_hi = np.percentile(z, 5), np.percentile(z, 95)
        max_elev_diff = float(z_hi - z_lo)

        # Best-fit plane via SVD
        centroid = cloud.mean(axis=0)
        centered = cloud - centroid
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            normal = vh[-1]
            # Slope = angle between normal and vertical axis
            cos_a = abs(float(normal[2])) / float(np.linalg.norm(normal))
            cos_a = min(1.0, cos_a)
            slope_rad = np.arccos(cos_a)
            slope_pct = float(np.tan(slope_rad) * 100)
            residuals = np.abs(centered @ normal)
            regularity = max(0, 100 - int(np.std(residuals) * 400))
        except np.linalg.LinAlgError:
            slope_pct = 0.0
            regularity = 50

        # Ground-plane area: convex hull of XZ projection (X forward, Z up in scene)
        estimated_area = 0.0
        if _SCIPY and n >= 4:
            try:
                hull = ConvexHull(cloud[:, :2])
                # scene units are arbitrary; apply a rough scale factor
                # (assumes ~0.5 m per scene unit for a typical hand-held scan)
                estimated_area = float(hull.volume) * 0.25
            except Exception:
                pass

        # Terrain classification
        if slope_pct < 5:
            terrain_type = "plano"
            foundation = "Losa o zapatas corridas — condiciones ideales"
        elif slope_pct < 15:
            terrain_type = "pendiente_suave"
            foundation = "Zapatas corridas con nivelación previa"
        elif slope_pct < 30:
            terrain_type = "pendiente_moderada"
            foundation = "Pilotes o muros de contención recomendados"
        else:
            terrain_type = "pendiente_pronunciada"
            foundation = "Estudio geotécnico especializado requerido"

        # Downsample point cloud for the API response (max 600 pts)
        idx = np.random.choice(n, min(600, n), replace=False)
        pc_sample = cloud[idx].tolist()

        return {
            "estimated_area_m2": round(estimated_area, 1),
            "slope_percentage": round(slope_pct, 1),
            "max_elevation_diff_m": round(max_elev_diff, 2),
            "surface_regularity_score": int(regularity),
            "scan_quality_score": int(scan_quality),
            "terrain_type": terrain_type,
            "recommended_foundation": foundation,
            "point_cloud": pc_sample,
            "total_points_detected": n,
            "frames_processed": n_frames,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resize(self, frame: np.ndarray, max_dim: int = 1280) -> np.ndarray:
        h, w = frame.shape[:2]
        if max(h, w) <= max_dim:
            return frame
        scale = max_dim / max(h, w)
        return cv2.resize(frame, (int(w * scale), int(h * scale)))

    def _single_frame_result(self, frame: np.ndarray) -> dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kps, _ = self.orb.detectAndCompute(gray, None)
        quality = min(100, len(kps) // 10)
        result = self._empty_result()
        result["scan_quality_score"] = quality
        result["error_message"] = (
            "Se recibió un único frame. Para análisis 3D completo, "
            "grabá un video o subí múltiples imágenes desde distintos ángulos."
        )
        return result

    def _empty_result(self, reason: Optional[str] = None) -> dict:
        return {
            "estimated_area_m2": 0.0,
            "slope_percentage": 0.0,
            "max_elevation_diff_m": 0.0,
            "surface_regularity_score": 0,
            "scan_quality_score": 0,
            "terrain_type": "indeterminado",
            "recommended_foundation": "Datos insuficientes para recomendación",
            "point_cloud": [],
            "total_points_detected": 0,
            "frames_processed": 0,
            "error_message": reason,
        }


# Singleton — imported by routers
terrain_analyzer = TerrainAnalyzer()
