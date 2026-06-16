"""HTTP routes for the architecture builder (from-scratch model design)."""
from __future__ import annotations

from fastapi import APIRouter

from . import service
from .schemas import (DENSE_FAMILIES, MOE_FAMILIES, ArchitectureSpec,
                      FeasibilityEstimate, SolveHiddenRequest)

router = APIRouter(prefix="/api/architect", tags=["architect"])


@router.get("/families")
def families():
    """Supported decoder families, split into dense and MoE."""
    return {"dense": list(DENSE_FAMILIES), "moe": list(MOE_FAMILIES)}


@router.post("/estimate", response_model=FeasibilityEstimate)
def estimate(spec: ArchitectureSpec):
    """Parameter count + memory feasibility verdict + warnings for a spec."""
    return service.estimate(spec)


@router.post("/solve-hidden")
def solve_hidden(req: SolveHiddenRequest):
    """Suggest a hidden_size landing near a target parameter count."""
    return service.solve_hidden(req)
