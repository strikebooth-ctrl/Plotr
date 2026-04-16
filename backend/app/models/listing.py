from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ListingMedia(Base):
    __tablename__ = "listing_media"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    file_path = Column(String, nullable=False)
    media_type = Column(String, nullable=False)  # photo | video | document
    file_name = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="media")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Ubicación
    direccion = Column(String, nullable=False)
    barrio = Column(String, nullable=False)
    localidad = Column(String, nullable=False, default="CABA")
    provincia = Column(String, nullable=False, default="Buenos Aires")
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)

    # Datos del terreno
    superficie_m2 = Column(Float, nullable=False)
    precio_usd = Column(Float, nullable=False)
    tipo_terreno = Column(String, nullable=False)   # baldío | con_construccion | industrial | rural
    uso_suelo = Column(String, nullable=False)       # residencial | comercial | mixto | industrial
    fot = Column(Float, nullable=True)
    altura_maxima_m = Column(Float, nullable=True)
    subsuelos_permitidos = Column(Integer, nullable=True)

    # Descripción y contacto
    descripcion = Column(Text, nullable=False)
    nombre_contacto = Column(String, nullable=False)
    telefono_contacto = Column(String, nullable=False)
    email_contacto = Column(String, nullable=False)

    # Estado
    estado = Column(String, default="disponible")   # disponible | reservado | vendido
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="listings")
    media = relationship("ListingMedia", back_populates="listing", cascade="all, delete-orphan")
    scan = relationship("TerrainScan", back_populates="listing", uselist=False)
