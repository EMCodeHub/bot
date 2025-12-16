from app.llm.ollama_client import (
    _extract_generated_text,
    _resolve_model_response_text,
)


def test_resolves_message_content():
    data = {"message": {"content": "  Hola mundo  "}}
    assert _resolve_model_response_text(data) == "Hola mundo"


def test_resolves_response_fallback():
    data = {"response": "  fallback text  "}
    assert _resolve_model_response_text(data) == "fallback text"


def test_extract_generated_text_from_choices():
    data = {
        "choices": [
            {"message": {"content": "  choice content  "}},
        ]
    }
    assert _extract_generated_text(data) == "choice content"
