# VPS deployment (Docker Compose)

This is the **production** stack, separate from the local dev `docker-compose.yml`.
It adds Nginx (TLS termination + media serving) and Certbot (Let's Encrypt) in front
of the same `web`/`db` services, and removes the dev-only bits (bind-mounted source,
hardcoded dev secrets, exposed Postgres port).

Files involved: `docker-compose.prod.yml`, `deploy/nginx/`, `deploy/init-letsencrypt.sh`,
`.env.production.example`. The app/Dockerfile itself are unchanged.

## 0. Prerequisites

- A VPS running Linux with Docker + the Docker Compose plugin installed
  (`docker compose version` should work).
- A domain's DNS **A record** (and AAAA if using IPv6) pointing at the VPS's public IP.
  Let's Encrypt validates over HTTP on port 80, so this must resolve before step 3.
- Ports 80 and 443 open on the VPS firewall.

## 1. Get the code onto the VPS

```bash
git clone <your-repo-url> erp && cd erp
```

## 2. Configure environment

```bash
cp .env.production.example .env
```

Edit `.env` and fill in every value — at minimum: `SECRET_KEY` (generate one, e.g.
`python3 -c "import secrets; print(secrets.token_urlsafe(50))"`), `DOMAIN`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `LETSENCRYPT_EMAIL`, `POSTGRES_PASSWORD` /
`DATABASE_URL` (keep them consistent), and `RESEND_API_KEY` for email.

If you don't have Cloudinary credentials yet, leave those three blank — uploaded
files will persist on a Docker volume on the VPS instead, served directly by nginx.

## 3. Issue the first TLS certificate

```bash
chmod +x deploy/init-letsencrypt.sh
./deploy/init-letsencrypt.sh
```

This starts a temporary self-signed cert so nginx can boot, requests the real
Let's Encrypt certificate via the HTTP-01 challenge, then reloads nginx. Run it
once — it's idempotent but unnecessary on subsequent deploys.

## 4. Bring the stack up

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The `web` container runs `migrate` automatically on start (see `Dockerfile`), and
static files were already collected at image-build time (served via whitenoise).

## 5. Create an admin user

```bash
docker compose -f docker-compose.prod.yml exec web \
  python management_system/manage.py createsuperuser
```

## 6. Keep certificates renewed

The `certbot` service in `docker-compose.prod.yml` checks for renewal every 12h
automatically, but nginx needs a reload to pick up a renewed certificate file.
Add a host crontab entry:

```cron
0 3 * * * cd /path/to/erp && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload >> /var/log/erp-nginx-reload.log 2>&1
```

## Redeploying after a code change

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

`db` data and `media_volume` persist across rebuilds since they're named volumes.

## Notes

- Postgres and gunicorn are **not** published to the host — only nginx (80/443) is
  publicly reachable; everything else talks over the internal compose network.
- To back up the database: `docker compose -f docker-compose.prod.yml exec db pg_dump -U <POSTGRES_USER> <POSTGRES_DB> > backup.sql`
- Local development is unaffected — keep using `docker compose up` with the
  existing `docker-compose.yml`.
