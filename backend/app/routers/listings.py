from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.listing import Listing, ListingMedia
from app.models.user import User
from app.schemas.listing import ListingOut
from app.services.file_storage import (
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    delete_file,
    save_upload,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/listings", tags=["listings"])

MAX_PHOTO_BYTES = settings.max_photo_size_mb * 1024 * 1024
MAX_VIDEO_BYTES = settings.max_video_size_mb * 1024 * 1024


def _validate_photos(files: List[UploadFile]) -> None:
    valid = [f for f in files if f.filename and f.filename.strip()]
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere al menos una foto del terreno (JPG, PNG, WEBP o HEIC).",
        )
    for f in valid:
        ext = Path(f.filename).suffix.lower()
        if ext not in PHOTO_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Formato de foto no válido: '{f.filename}'. Usá JPG, PNG, WEBP o HEIC.",
            )
        if f.size and f.size > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"La foto '{f.filename}' supera el límite de {settings.max_photo_size_mb} MB.",
            )


def _validate_videos(files: List[UploadFile]) -> None:
    valid = [f for f in files if f.filename and f.filename.strip()]
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere al menos un video del terreno (MP4, MOV, AVI o WEBM).",
        )
    for f in valid:
        ext = Path(f.filename).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Formato de video no válido: '{f.filename}'. Usá MP4, MOV, AVI o WEBM.",
            )
        if f.size and f.size > MAX_VIDEO_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"El video '{f.filename}' supera el límite de {settings.max_video_size_mb} MB.",
            )


@router.post("/", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    # ── Campos del formulario ──────────────────────────────────────────
    direccion: str = Form(...),
    barrio: str = Form(...),
    localidad: str = Form("CABA"),
    provincia: str = Form("Buenos Aires"),
    latitud: Optional[float] = Form(None),
    longitud: Optional[float] = Form(None),
    superficie_m2: float = Form(...),
    precio_usd: float = Form(...),
    tipo_terreno: str = Form(..., description="baldío | con_construccion | industrial | rural"),
    uso_suelo: str = Form(..., description="residencial | comercial | mixto | industrial"),
    fot: Optional[float] = Form(None),
    altura_maxima_m: Optional[float] = Form(None),
    subsuelos_permitidos: Optional[int] = Form(None),
    descripcion: str = Form(...),
    nombre_contacto: str = Form(...),
    telefono_contacto: str = Form(...),
    email_contacto: str = Form(...),
    # ── Archivos (fotos y videos OBLIGATORIOS) ─────────────────────────
    fotos: List[UploadFile] = File(..., description="Fotos del terreno — obligatorio, mín. 1"),
    videos: List[UploadFile] = File(..., description="Videos del terreno — obligatorio, mín. 1"),
    documentos: Optional[List[UploadFile]] = File(
        None, description="Planos, escrituras, informe de dominio — opcional"
    ),
    # ── Auth ──────────────────────────────────────────────────────────
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validaciones de negocio
    if superficie_m2 <= 0:
        raise HTTPException(422, "La superficie debe ser mayor a 0")
    if precio_usd <= 0:
        raise HTTPException(422, "El precio debe ser mayor a 0")

    _validate_photos(fotos)
    _validate_videos(videos)

    listing = Listing(
        owner_id=current_user.id,
        direccion=direccion,
        barrio=barrio,
        localidad=localidad,
        provincia=provincia,
        latitud=latitud,
        longitud=longitud,
        superficie_m2=superficie_m2,
        precio_usd=precio_usd,
        tipo_terreno=tipo_terreno,
        uso_suelo=uso_suelo,
        fot=fot,
        altura_maxima_m=altura_maxima_m,
        subsuelos_permitidos=subsuelos_permitidos,
        descripcion=descripcion,
        nombre_contacto=nombre_contacto,
        telefono_contacto=telefono_contacto,
        email_contacto=email_contacto,
    )
    db.add(listing)
    db.flush()  # obtener listing.id antes del commit

    subdir = f"listings/{listing.id}"

    for foto in [f for f in fotos if f.filename]:
        path, size = await save_upload(foto, f"{subdir}/fotos")
        db.add(
            ListingMedia(
                listing_id=listing.id,
                file_path=path,
                media_type="photo",
                file_name=foto.filename,
                file_size_bytes=size,
            )
        )

    for video in [v for v in videos if v.filename]:
        path, size = await save_upload(video, f"{subdir}/videos")
        db.add(
            ListingMedia(
                listing_id=listing.id,
                file_path=path,
                media_type="video",
                file_name=video.filename,
                file_size_bytes=size,
            )
        )

    if documentos:
        for doc in [d for d in documentos if d and d.filename]:
            path, size = await save_upload(doc, f"{subdir}/docs")
            db.add(
                ListingMedia(
                    listing_id=listing.id,
                    file_path=path,
                    media_type="document",
                    file_name=doc.filename,
                    file_size_bytes=size,
                )
            )

    db.commit()
    db.refresh(listing)
    return listing


@router.get("/", response_model=List[ListingOut])
def list_listings(
    barrio: Optional[str] = None,
    tipo_terreno: Optional[str] = None,
    uso_suelo: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    superficie_min: Optional[float] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    q = db.query(Listing).filter(Listing.is_active == True)
    if barrio:
        q = q.filter(Listing.barrio.ilike(f"%{barrio}%"))
    if tipo_terreno:
        q = q.filter(Listing.tipo_terreno == tipo_terreno)
    if uso_suelo:
        q = q.filter(Listing.uso_suelo == uso_suelo)
    if precio_min is not None:
        q = q.filter(Listing.precio_usd >= precio_min)
    if precio_max is not None:
        q = q.filter(Listing.precio_usd <= precio_max)
    if superficie_min is not None:
        q = q.filter(Listing.superficie_m2 >= superficie_min)
    return q.order_by(Listing.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.is_active == True)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Terreno no encontrado")
    return listing


@router.patch("/{listing_id}/estado")
def update_estado(
    listing_id: int,
    estado: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = {"disponible", "reservado", "vendido"}
    if estado not in allowed:
        raise HTTPException(422, f"Estado inválido. Opciones: {allowed}")
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Terreno no encontrado")
    if listing.owner_id != current_user.id:
        raise HTTPException(403, "Sin permiso")
    listing.estado = estado
    db.commit()
    return {"id": listing_id, "estado": estado}


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Terreno no encontrado")
    if listing.owner_id != current_user.id:
        raise HTTPException(403, "Sin permiso")
    for media in listing.media:
        delete_file(media.file_path)
    listing.is_active = False
    db.commit()
