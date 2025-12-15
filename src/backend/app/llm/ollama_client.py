import requests
from app.config import settings


def generate_response(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """
    Call Ollama's /generate endpoint with a prompt and return the full response text.
    """
    url = f"{settings.ollama_url}/api/generate"
    model_name = model or settings.ollama_model

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,  # keep it simple for now
        "temperature": temperature if temperature is not None else settings.ollama_temperature,
        "top_p": top_p if top_p is not None else settings.ollama_top_p,
    }

    try:
        # long prompts / context from RAG sometimes take a while; give Ollama up to 5 minutes
        res = requests.post(
            url,
            json=payload,
            timeout=settings.ollama_generate_timeout,
        )
        res.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Error calling Ollama: {e}")

    data = res.json()
    return data.get("response", "").strip()
