# Despliegue en Contabo (Ubuntu)

Arrancas desde el shell del VPS como `root@vmi2970910:~#`; cada bloque de comandos se puede pegar tal cual.

1. **Actualizar el sistema e instalar dependencias básicas**
   ```bash
   apt update && apt upgrade -y
   apt install -y ca-certificates curl gnupg lsb-release git
   ```

2. **Instalar Docker y Docker Compose**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   apt install -y docker-compose-plugin
   systemctl enable --now docker
   ```
   Comprueba:
   ```bash
   docker version
   docker compose version
   ```

3. **Clonar el repositorio y preparar variables**
   ```bash
   git clone <repo-url> bot
   cd bot
   cp .env.example .env
   ```
   Ajusta `.env` si necesitas otros datos para `POSTGRES_*`, `OLLAMA_*` o SMTP; en especial puedes fijar:
   - `OLLAMA_BASE_URL` (o el legado `OLLAMA_URL`)
   - `OLLAMA_CHAT_MODEL` / `OLLAMA_EMBED_MODEL`
   - `OLLAMA_TIMEOUT` para darle más tiempo a Ollama que suba los modelos.
  Puedes afinar cuánto espera el backend antes de dar error al conectarse con Postgres añadiendo:
  ```ini
  DB_CONN_RETRIES=10
  DB_CONN_RETRY_DELAY=2.0
  ```
  (estas variables no son estrictas, sirven para dar tiempo al contenedor de Postgres).

4. **Levantar la pila en segundo plano**
   ```bash
   docker compose up -d --build
   ```
   - `postgres` se inicializa con pgvector y mantiene su volumen `pgdata`.
   - `ollama` corre el servidor de modelos en el contenedor `bot-ollama`.
   - `backend` construye la imagen con `uvicorn` apuntando a `app.main` desde `/workspace/src/backend`.

5. **Crear la extensión pgvector**
   ```bash
   docker compose exec postgres psql -U postgres -d mydb -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

6. **Descargar los modelos Ollama**
   ```bash
   docker compose exec ollama ollama pull llama3
   docker compose exec ollama ollama pull nomic-embed-text
   ```
   Añade otros modelos que uses en `.env`, por ejemplo `phi3`, y repite el `ollama pull <modelo>`.

7. **Ingestar la base de conocimiento**
   ```bash
   docker compose run --rm backend python src/ingestion/ingest.py
   ```
   Este script recorre `src/knowledge_base`, obtiene vectores con Ollama y persiste cada chunk en la tabla `documents` de Postgres.

8. **Verificar health**
   - Desde el VPS: `curl http://localhost:8000/health` debe responder `200`.
   - Desde tu máquina local: `curl http://62.171.150.191:8000/health`.

9. **Comandos útiles de operación**
   ```bash
   docker compose logs -f backend
   docker compose restart backend
   docker compose ps
   docker compose down            # al terminar o para limpiar
   docker compose down --volumes  # borra datos persistentes
   ```

10. **Notas adicionales**
    - Si `src/knowledge_base` no existe dentro del repo, clónalo o copia los archivos antes de ejecutar la ingesta para evitar `FileNotFoundError`.
    - El backend ya no depende de rutas Windows: monta la carpeta en `/workspace/src/knowledge_base` y usa `PYTHONPATH=/workspace/src/backend`.
    - El cliente Ollama intenta `/api/generate` y `/api/chat` para generación, y `/api/embed` antes de `/api/embeddings` para vectores; revisa los logs (`docker compose logs backend`) si hay 404 y el helper se ajusta automáticamente.
