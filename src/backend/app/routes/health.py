from fastapi import APIRouter

from app.llm.ollama_client import get_ollama_health

router = APIRouter(prefix="", tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok", "ollama": get_ollama_health()}
