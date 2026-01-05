"""Chat endpoints for orchestrating academic conversations."""
from fastapi import APIRouter

from ...orchestrator.router import AgentRouter

router = APIRouter(prefix="/chat", tags=["chat"])
agent_router = AgentRouter()


@router.post("/")
async def handle_chat(payload: dict) -> dict:
    """Entrypoint for user prompts.

    Payload intentionally typed as dict for skeleton simplicity. In real
    implementation this would be a Pydantic model describing the session
    context and message metadata.
    """
    response = await agent_router.route(payload)
    return {"result": response}
