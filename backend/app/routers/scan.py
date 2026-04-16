"""
Terrain 3D scan router.

Mobile flow:
  1. User taps "Escanear terreno" → camera opens on the frontend.
  2. User records a video (or captures multiple photos) while walking around the land.
  3. Frontend POSTs the file(s) to POST /scan/.
  4. Backend saves files, creates a TerrainScan record (status=processing),
     and queues analysis as a background task.
  5. Frontend polls GET /scan/{id} until status == "completed".
  6. Response includes point_cloud (list of [x,y,z] triplets) + all terrain metrics
     ready for 3D rendering on the client.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.scan import TerrainScan
from app.models.user import User
from app.schemas.scan import ScanOut
from app.services.file_storage import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS, full_path, save_upload
from app.services.terrain_analysis import terrain_analyzer
from app.utils.security import get_current_user

router = APIRouter(prefix="/scan", tags=["scan"])


# ------------------------------------------------------------------
# Background task — runs in a thread-pool worker
# ------------------------------------------------------------------

def _run_analysis(scan_id: int) -> None:
    db = SessionLocal()
    try:
        scan = db.query(TerrainScan).filter(TerrainScan.id == scan_id).first()
        if not scan:
            return

        abs_paths = [full_path(p) for p in scan.file_paths]
        results = terrain_analyzer.analyze_from_paths(abs_paths)

        scan.frames_processed = results.get("frames_processed", 0)
        scan.estimated_area_m2 = results.get("estimated_area_m2")
        scan.slope_percentage = results.get("slope_percentage")
        scan.max_elevation_diff_m = results.get("max_elevation_diff_m")
        scan.surface_regularity_score = results.get("surface_regularity_score")
        scan.scan_quality_score = results.get("scan_quality_score")
        scan.terrain_type = results.get("terrain_type")
        scan.recommended_foundation = results.get("recommended_foundation")
        scan.point_cloud = results.get("point_cloud")
        scan.total_points_detected = results.get("total_points_detected")
        scan.error_message = results.get("error_message")
        scan.status = "completed"
        scan.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        try:
            scan.status = "failed"
            scan.error_message = str(exc)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def create_scan(
    background_tasks: BackgroundTasks,
    listing_id: Optional[int] = Form(None, description="Asociar a un terreno publicado (opcional)"),
    archivos: List[UploadFile] = File(
        ...,
        description="Video(s) o imágenes capturadas con la cámara del celular. "
                    "Para mejor resultado: grabá un video de 15-30 segundos "
                    "dando una vuelta lenta alrededor del terreno.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not archivos:
        raise HTTPException(422, "Se requiere al menos un archivo de escaneo")

    file_paths: List[str] = []
    has_video = False

    for archivo in archivos:
        ext = Path(archivo.filename or "").suffix.lower()
        if ext not in VIDEO_EXTENSIONS and ext not in PHOTO_EXTENSIONS:
            raise HTTPException(
                422,
                f"Formato no soportado: '{archivo.filename}'. "
                "Usá MP4, MOV, JPG, PNG u otro formato estándar.",
            )
        if ext in VIDEO_EXTENSIONS:
            has_video = True
        path, _ = await save_upload(archivo, f"scans/{current_user.id}")
        file_paths.append(path)

    scan = TerrainScan(
        owner_id=current_user.id,
        listing_id=listing_id,
        source_type="video" if has_video else "images",
        file_paths=file_paths,
        status="processing",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    background_tasks.add_task(_run_analysis, scan.id)
    return scan


@router.get("/", response_model=List[ScanOut])
def list_scans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(TerrainScan)
        .filter(TerrainScan.owner_id == current_user.id)
        .order_by(TerrainScan.created_at.desc())
        .all()
    )


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan = (
        db.query(TerrainScan)
        .filter(TerrainScan.id == scan_id, TerrainScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(404, "Escaneo no encontrado")
    return scan
