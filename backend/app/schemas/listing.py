from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime


class ListingMediaOut(BaseModel):
    id: int
    media_type: str
    file_name: str
    file_size_bytes: int
    file_path: str

    model_config = {"from_attributes": True}


class ListingCreate(BaseModel):
    direccion: str
    barrio: str
    localidad: str = "CABA"
    provincia: str = "Buenos Aires"
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    superficie_m2: float
    precio_usd: float
    tipo_terreno: str   # baldío | con_construccion | industrial | rural
    uso_suelo: str      # residencial | comercial | mixto | industrial
    fot: Optional[float] = None
    altura_maxima_m: Optional[float] = None
    subsuelos_permitidos: Optional[int] = None
    descripcion: str
    nombre_contacto: str
    telefono_contacto: str
    email_contacto: EmailStr

    @field_validator("superficie_m2", "precio_usd")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Debe ser mayor a 0")
        return v


class ListingOut(BaseModel):
    id: int
    direccion: str
    barrio: str
    localidad: str
    provincia: str
    latitud: Optional[float]
    longitud: Optional[float]
    superficie_m2: float
    precio_usd: float
    tipo_terreno: str
    uso_suelo: str
    fot: Optional[float]
    altura_maxima_m: Optional[float]
    subsuelos_permitidos: Optional[int]
    descripcion: str
    nombre_contacto: str
    telefono_contacto: str
    email_contacto: str
    estado: str
    created_at: datetime
    media: List[ListingMediaOut] = []

    model_config = {"from_attributes": True}
