from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.listing import Listing
from app.schemas.listing import ListingOut

router = APIRouter(prefix="/capital-matcher", tags=["capital_matcher"])


class CapitalMatchRequest(BaseModel):
    capital_usd: float
    barrios: Optional[List[str]] = None
    tipo_terreno: Optional[str] = None
    uso_suelo: Optional[str] = None
    superficie_min_m2: Optional[float] = None
    fot_min: Optional[float] = None
    # Tolerance: listings priced within ±tolerance_pct of capital are considered
    tolerance_pct: float = 0.40


class MatchResult(BaseModel):
    listing: ListingOut
    compatibility_score: float  # 0–100, higher = better match
    price_ratio: float          # listing.precio_usd / capital_usd

    model_config = {"from_attributes": True}


@router.post("/", response_model=List[MatchResult])
def match_capital(req: CapitalMatchRequest, db: Session = Depends(get_db)):
    if req.capital_usd <= 0:
        return []

    price_min = req.capital_usd * (1 - req.tolerance_pct)
    price_max = req.capital_usd * (1 + req.tolerance_pct)

    q = db.query(Listing).filter(
        Listing.is_active == True,
        Listing.precio_usd >= price_min,
        Listing.precio_usd <= price_max,
    )

    if req.barrios:
        q = q.filter(or_(*[Listing.barrio.ilike(f"%{b}%") for b in req.barrios]))
    if req.tipo_terreno:
        q = q.filter(Listing.tipo_terreno == req.tipo_terreno)
    if req.uso_suelo:
        q = q.filter(Listing.uso_suelo == req.uso_suelo)
    if req.superficie_min_m2:
        q = q.filter(Listing.superficie_m2 >= req.superficie_min_m2)
    if req.fot_min:
        q = q.filter(Listing.fot >= req.fot_min)

    listings = q.limit(50).all()

    results: List[MatchResult] = []
    for listing in listings:
        ratio = listing.precio_usd / req.capital_usd
        # Score peaks at ratio == 1.0 (exact budget match) and drops linearly
        score = max(0.0, 100.0 - abs(ratio - 1.0) * (100.0 / req.tolerance_pct))
        results.append(
            MatchResult(
                listing=ListingOut.model_validate(listing),
                compatibility_score=round(score, 1),
                price_ratio=round(ratio, 3),
            )
        )

    results.sort(key=lambda r: r.compatibility_score, reverse=True)
    return results
