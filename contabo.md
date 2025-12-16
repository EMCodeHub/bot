# Despliegue en VPS Contabo

1. **Preparar el entorno**
   - Copia `.env.example` a `.env` y ajusta las variables sensibles (`DB_*`, `OLLAMA_*`, correo, etc.).
   - Asegúrate de que el directorio `src/knowledge_base` contiene los `.md` que se van a ingerir.
   - Instala Docker y Docker Compose si no están presentes.

2. **Descargar imágenes**
   ```bash
   docker pull pgvector/pgvector:pg16
   docker pull ollama/ollama:latest
   ```
   (Esto evita el retraso de descargar 2 GB durante `docker compose up`.)

3. **Lanzar el stack**
   ```bash
   docker compose down -v
   docker compose up -d --build
   ```
   - El backend depende de Postgres y Ollama sanos; el `healthcheck` de Ollama invoca `ollama list`.
   - Si Ollama no tiene los modelos, llegarán errores 404: corre `docker compose exec ollama /usr/bin/ollama pull llama3 nomic-embed-text`.

4. **Verificar la ingestión**
   ```bash
   docker compose run --rm backend python src/ingestion/ingest.py
   ```
   - Usa los mismos `request_embedding_vector` que el chat; ahora el cliente incorpora reintentos y errores claros.
   - El endpoint `/health` devolverá el estado de Ollama (`/api/chat` y `/api/embeddings`).

5. **Mantener actualizado**
   - Para aplicar cambios o reiniciar, repite `docker compose down -v && docker compose up -d --build`.
   - Si actualizas Ollama, vuelve a `ollama pull` los modelos antes de reiniciar el backend.

6. **Precauciones adicionales**
   - El backend utiliza timeouts largos (>2 min) para `/api/chat` y `/api/embeddings`; evita detener el contenedor de Ollama durante ese tiempo porque el backend esperará a que los modelos carguen antes de responder.
   - Antes de arrancar el stack, confirma que `.env` tiene los nuevos campos `OLLAMA_CONNECT_TIMEOUT`, `OLLAMA_RETRY_ATTEMPTS` y `OLLAMA_RETRY_BACKOFF` con los valores deseados para producción.
   - Monitorea `docker compose logs backend` la primera vez después de `up -d` para asegurarte de que los modelos se cargan sin errores de `OllamaRequestError`.
   - Si el VPS se reinicia, aplica explícitamente `ollama pull llama3 nomic-embed-text` de nuevo antes de arracar el backend para evitar fallos 404 por modelos ausentes.
