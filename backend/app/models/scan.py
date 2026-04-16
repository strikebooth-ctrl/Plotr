from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class TerrainScan(Base):
    __tablename__ = "terrain_scans"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True)

    # Input
    source_type = Column(String, nullable=False)    # video | images
    file_paths = Column(JSON, nullable=False)
    frames_processed = Column(Integer, default=0)

    # Resultados del análisis 3D
    status = Column(String, default="processing")   # processing | completed | failed
    estimated_area_m2 = Column(Float, nullable=True)
    slope_percentage = Column(Float, nullable=True)
    max_elevation_diff_m = Column(Float, nullable=True)
    surface_regularity_score = Column(Integer, nullable=True)
    scan_quality_score = Column(Integer, nullable=True)
    terrain_type = Column(String, nullable=True)
    recommended_foundation = Column(Text, nullable=True)
    point_cloud = Column(JSON, nullable=True)        # muestra de puntos 3D para visualización
    total_points_detected = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="scans")
    listing = relationship("Listing", back_populates="scan")
