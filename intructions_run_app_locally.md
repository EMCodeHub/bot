PS C:\Users\edume\OneDrive\Escritorio\bot>  

REM 1. Copy the shared .env template so every container reads the same secrets.
if (-not (Test-Path .env)) { copy .env.example .env }

REM 2. Build and start the entire stack (Postgres + Ollama + backend) inside Docker.
docker compose up -d --build

REM 3. Enable the pgvector extension inside Postgres.
docker compose exec postgres psql -U postgres -d mydb -c "CREATE EXTENSION IF NOT EXISTS vector;"

REM 4. Pull the required Ollama models inside the Ollama container.
docker compose exec ollama ollama pull phi3
docker compose exec ollama ollama pull llama3
docker compose exec ollama ollama pull nomic-embed-text

REM 5. Ingest the knowledge base from the backend container so Ollama + Postgres share the same network.

docker compose exec backend python /workspace/src/ingestion/ingest.py


REM 6. Watch logs from any service (optional).

docker compose logs -f backend

REM 7. Access the API at http://localhost:8000 (reload is handled inside Docker).

REM 8. When you are done, tear everything down.
docker compose down



to reset de backend:  docker compose restart backend


