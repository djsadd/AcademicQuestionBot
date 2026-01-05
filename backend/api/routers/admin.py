"""Admin endpoints for operational tasks."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
async def healthcheck() -> dict:
    """Simple readiness check used by Docker/K8s probes."""
    return {"status": "ok"}
