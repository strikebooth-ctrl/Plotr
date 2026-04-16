import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine

# Import models so SQLAlchemy registers them before create_all()
from app.models import User, Listing, ListingMedia, TerrainScan  # noqa: F401

from app.routers import auth, listings, scan, parcels, capital_matcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield


app = FastAPI(
    title="Plotr API",
    description=(
        "Backend para análisis técnico de terrenos — Plotr.\n\n"
        "Incluye: autenticación, publicación de terrenos (con fotos y videos obligatorios), "
        "escaneo 3D por cámara (Structure-from-Motion con OpenCV), "
        "consulta de parcelas catastrales y calculadora de capital."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restringir a dominios específicos en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(scan.router)
app.include_router(parcels.router)
app.include_router(capital_matcher.router)

# Serve uploaded media files at /uploads/<path>
if os.path.isdir(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "Plotr API", "version": "1.0.0"}
