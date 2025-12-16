from typing import List, Optional

from pydantic import Extra, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama configuration
    ollama_base_url: str = Field(
        "http://ollama:11434", env=["OLLAMA_BASE_URL", "OLLAMA_URL"]
    )
    ollama_chat_model: str = Field(
        "llama3", env=["OLLAMA_CHAT_MODEL", "OLLAMA_MODEL"]
    )
    ollama_embed_model: str = Field(
        "nomic-embed-text", env=["OLLAMA_EMBED_MODEL", "EMBEDDING_MODEL"]
    )
    ollama_timeout: float = Field(120.0, env="OLLAMA_TIMEOUT")
    ollama_generate_timeout: float = Field(300.0, env="OLLAMA_GENERATE_TIMEOUT")
    ollama_health_timeout: float = Field(5.0, env="OLLAMA_HEALTH_TIMEOUT")
    ollama_http_retries: int = Field(3, env="OLLAMA_RETRY_ATTEMPTS")
    ollama_retry_backoff: float = Field(1.0, env="OLLAMA_RETRY_BACKOFF")
    ollama_temperature: float = 0.0
    ollama_top_p: float = 1.0

    # Embedding metadata
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_version: str = "1.0"
    embedding_chunk_size: int = 500
    embedding_chunk_overlap: int = 50
    embedding_similarity_metric: str = "cosine"
    rag_min_similarity: float = 0.6

    # Database connection parameters
    db_host: str = Field(..., env="DB_HOST")
    db_port: int = Field(..., env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")

    # Email delivery
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_ssl: bool = False
    smtp_use_tls: bool = True
    smtp_timeout: float = 10.0
    lead_notification_from: str = "no-reply@medtl.ai"
    lead_notification_subject: str = "New chatbot lead captured"
    lead_notification_recipients: List[str] = [
        "eduardo.mediavilla@medifestructuras.com",
        "eduardo.mediavilla@medifestructuras.com",
    ]
    lead_notification_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra=Extra.ignore,
    )


settings = Settings()
