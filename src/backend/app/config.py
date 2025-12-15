from typing import List, Optional

from pydantic import Extra
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"  # phi3  #  llama3
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_version: str = "1.0"
    embedding_chunk_size: int = 500
    embedding_chunk_overlap: int = 50
    embedding_similarity_metric: str = "cosine"
    ollama_timeout: float = 60.0
    ollama_generate_timeout: float = 300.0
    ollama_temperature: float = 0.0
    ollama_top_p: float = 1.0
    rag_min_similarity: float = 0.6

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_ssl: bool = False
    smtp_use_tls: bool = True
    smtp_timeout: float = 10.0
    lead_notification_from: str = "no-reply@medtl.ai"
    lead_notification_subject: str = "New chatbot lead captured"
    lead_notification_recipients: List[str] = ["eduardo.mediavilla@medifestructuras.com", "eduardo.mediavilla@medifestructuras.com"]
    lead_notification_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra=Extra.ignore,
    )


settings = Settings()
