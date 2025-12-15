## Deployment on Contabo VPS

1. **Provision the VPS** – order an Ubuntu 24.04 (LTS) instance on Contabo with the CPU/RAM you need. Enable SSH and note the public IP.
2. **Harden the system** (optional but recommended):
   - Log in via SSH and create a non-root sudo user.
   - Enable the firewall with `sudo ufw allow OpenSSH`, then `sudo ufw enable`.
   - Install security updates: `sudo apt update && sudo apt upgrade -y`.
3. **Install container tooling**:
   ```
   sudo apt install -y ca-certificates curl gnupg lsb-release git
   sudo mkdir -p /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
   sudo apt update
   sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo usermod -aG docker $USER
   ```
   After this logout/login so that `docker` works without sudo.
4. **Clone the repository**:
   ```
   git clone <your-repo-url> medif-bot && cd medif-bot
   ```
5. **Prepare the environment**:
   - Copy the template: `cp .env.example .env`.
   - Edit `.env` with production secrets (Postgres password, Ollama key if needed, Stripe/SMTP credentials, allowed hosts, etc.).
   - Ensure `PGHOST`, `PGPASSWORD`, `DATABASE_URL` and other variables are set for the VPS network.
6. **Start the stack**:
   ```
   docker compose up -d --build
   ```
7. **Initialize Postgres**:
   ```
   docker compose exec postgres psql -U postgres -d mydb -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```
8. **Pull Ollama models** (only needs to be done once or when models change):
   ```
   docker compose exec ollama ollama pull phi3
   docker compose exec ollama ollama pull
   docker compose exec ollama ollama pull nomic-embed-text
   ```
9. **Ingest the knowledge base**:
   ```
   docker compose exec backend python /workspace/src/ingestion/ingest.py
   ```
   Re-run this command every time you update Markdown so the embeddings stay fresh.
10. **Configure a reverse proxy (optional)** – install Nginx, configure it to proxy HTTP/HTTPS to `localhost:8000`, and obtain certificates via Certbot for your domain.
11. **Persistent data & backups**:
   - Docker Compose already mounts volumes for Postgres and Ollama data. Back them up via `docker compose exec postgres pg_dump` or by copying the volume.
12. **Monitoring & maintenance**:
   - View backend logs: `docker compose logs -f backend`.
   - Restart services: `docker compose restart backend` or rebuild with `docker compose up -d --build`.
   - Update code by pulling from Git and rerunning steps 6‑9.

Keep the firewall open only on necessary ports (SSH, HTTP/HTTPS) and rotate secrets periodically. With this workflow, you can keep your Contabo VPS running the bot stack reliably.
