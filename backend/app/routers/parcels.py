"""
Parcel lookup router.

Integrates (or stubs) three official Argentine data sources:
  - API Código Urbanístico CABA  → datos.buenosaires.gob.ar
  - SEGEMAR                      → geotechnical / geological data
  - ARBA + Catastro Nacional     → cadastral / domain status

Replace the stub in _fetch_parcel_data() with real HTTP calls once API keys are available.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/parcels", tags=["parcels"])


class ParcelLookupRequest(BaseModel):
    direccion: Optional[str] = None
    smp: Optional[str] = None  # Sección-Manzana-Parcela (número catastral)


class ParcelData(BaseModel):
    direccion: str
    barrio: str
    smp: str
    superficie_m2: float

    # Normativa urbanística (Código Urbanístico CABA)
    fot: float
    altura_maxima_m: float
    uso_suelo: str
    subsuelos_permitidos: int

    # Geotecnia (SEGEMAR + Ciudad 3D GCBA)
    napa_freatia_m: Optional[float]
    tipo_suelo: str
    riesgo_hidrico: str

    # Catastral (ARBA + Catastro Nacional)
    propietario_tipo: str   # Particular | Empresa | Sucesión | Estado
    estado_dominio: str
    afectaciones: List[str]

    fuente: str


def _fetch_parcel_data(direccion: Optional[str], smp: Optional[str]) -> ParcelData:
    """
    TODO: Replace this stub with real API calls:

      Normativa:
        GET https://datos.buenosaires.gob.ar/api/3/action/datastore_search
            ?resource_id=<codigo-urbanistico-resource-id>
            &q=<direccion>

      Geotécnica:
        GET https://ide.segemar.gob.ar/arcgis/rest/services/...
            ?geometry=<lon,lat>&outFields=*&f=json

      Catastral:
        GET https://epok.buenosaires.gob.ar/catastro/parcela/?
            direccion=<direccion>

    For now returns representative sample data so the frontend can be developed
    against a real API shape.
    """
    return ParcelData(
        direccion=direccion or "Dirección ingresada",
        barrio="Palermo",
        smp=smp or "001-054-012A",
        superficie_m2=300.0,
        fot=3.5,
        altura_maxima_m=24.0,
        uso_suelo="Residencial con PB comercial",
        subsuelos_permitidos=2,
        napa_freatia_m=6.5,
        tipo_suelo="Limo arcilloso consolidado",
        riesgo_hidrico="Bajo",
        propietario_tipo="Particular",
        estado_dominio="Sin afectaciones registradas",
        afectaciones=[],
        fuente="API CABA · SEGEMAR · ARBA (stub dev)",
    )


@router.post("/lookup", response_model=ParcelData)
def lookup_parcel(req: ParcelLookupRequest):
    if not req.direccion and not req.smp:
        raise HTTPException(
            status_code=422,
            detail="Proporcioná al menos una dirección o número catastral (SMP).",
        )
    return _fetch_parcel_data(req.direccion, req.smp)


@router.get("/barrios", response_model=List[str])
def list_barrios():
    """Devuelve los 48 barrios de CABA para autocompletar formularios."""
    return [
        "Agronomía", "Almagro", "Balvanera", "Barracas", "Belgrano",
        "Boedo", "Caballito", "Chacarita", "Coghlan", "Colegiales",
        "Constitución", "Flores", "Floresta", "La Boca", "La Paternal",
        "Liniers", "Mataderos", "Monte Castro", "Montserrat", "Nueva Pompeya",
        "Núñez", "Palermo", "Parque Avellaneda", "Parque Chacabuco",
        "Parque Chas", "Parque Patricios", "Puerto Madero", "Recoleta",
        "Retiro", "Saavedra", "San Cristóbal", "San Nicolás", "San Telmo",
        "Vélez Sársfield", "Versalles", "Villa Crespo", "Villa del Parque",
        "Villa Devoto", "Villa General Mitre", "Villa Lugano", "Villa Luro",
        "Villa Ortúzar", "Villa Pueyrredón", "Villa Real", "Villa Riachuelo",
        "Villa Santa Rita", "Villa Soldati", "Villa Urquiza",
    ]
