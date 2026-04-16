from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ScanOut(BaseModel):
    id: int
    status: str
    source_type: str
    frames_processed: int
    estimated_area_m2: Optional[float]
    slope_percentage: Optional[float]
    max_elevation_diff_m: Optional[float]
    surface_regularity_score: Optional[int]
    scan_quality_score: Optional[int]
    terrain_type: Optional[str]
    recommended_foundation: Optional[str]
    point_cloud: Optional[List[Any]]
    total_points_detected: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
