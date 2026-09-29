# Oracle Cloud deployment

This deployment keeps PostgreSQL, Redis, and FastAPI's port 8000 private. Caddy is
the only internet-facing container and publishes ports 80 and 443.

## Server prerequisites

On the Ubuntu VM:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
exit
```

Reconnect over SSH so the Docker group membership takes effect.

## Clone and configure

```bash
git clone https://github.com/esravar/cloud-ai-meeting-intelligence.git
cd cloud-ai-meeting-intelligence
git switch meeting-intelligence-v2
cp .env.production.example .env
```

Generate URL-safe secrets on the server:

```bash
openssl rand -hex 32
openssl rand -hex 32
python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
```

Use the first value for `POSTGRES_PASSWORD`, the second for `APP_SECRET_KEY`,
and the Base64 value for `FIELD_ENCRYPTION_KEY`. Edit the remaining values:

```bash
nano .env
```

Never commit `.env` or paste its contents into an issue or chat.

## DNS and firewall

Create a Cloudflare DNS `A` record named `api` that points to the VM public IPv4.
Keep it **DNS only** until Caddy obtains the first certificate. Allow inbound TCP
ports 22, 80, and 443 in the OCI security list. Do not expose 5432, 6379, or 8000.

## Start and verify

```bash
docker compose -f docker-compose.production.yml config
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f api worker caddy
```

Verify from another terminal:

```bash
curl https://api.esravar.com/health
```

After HTTPS works, Netlify should use:

```text
VITE_API_BASE_URL=https://api.esravar.com
```

## Updating

```bash
git pull --ff-only
docker compose -f docker-compose.production.yml up -d --build
```

## Database backup

```bash
mkdir -p "$HOME/backups"
docker compose -f docker-compose.production.yml exec -T db \
  pg_dump -U meeting -d meeting_intelligence -Fc \
  > "$HOME/backups/meeting-intelligence-$(date +%F-%H%M).dump"
```
