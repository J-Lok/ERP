#!/bin/bash
# One-time bootstrap: obtains the first Let's Encrypt certificate for DOMAIN.
# Run this once from the repo root on the VPS, after `.env` is filled in and
# BEFORE the first `docker compose -f docker-compose.prod.yml up -d`.
#
# After this succeeds, the `certbot` service in docker-compose.prod.yml keeps
# the certificate renewed automatically. Nginx still needs a reload after a
# renewal picks up a new cert — see DEPLOY.md for the cron entry.
set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
CERTBOT_CONF="./deploy/certbot/conf"
CERTBOT_WWW="./deploy/certbot/www"
RSA_KEY_SIZE=4096

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.production.example to .env and fill it in first." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

if [ -z "${DOMAIN:-}" ]; then
  echo "DOMAIN is not set in .env" >&2
  exit 1
fi

if [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "LETSENCRYPT_EMAIL is not set in .env" >&2
  exit 1
fi

mkdir -p "$CERTBOT_CONF" "$CERTBOT_WWW"

if [ ! -e "$CERTBOT_CONF/options-ssl-nginx.conf" ] || [ ! -e "$CERTBOT_CONF/ssl-dhparam.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
    -o "$CERTBOT_CONF/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
    -o "$CERTBOT_CONF/ssl-dhparam.pem"
fi

echo "### Creating dummy self-signed certificate for $DOMAIN so nginx can start ..."
mkdir -p "$CERTBOT_CONF/live/$DOMAIN"
openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
  -keyout "$CERTBOT_CONF/live/$DOMAIN/privkey.pem" \
  -out "$CERTBOT_CONF/live/$DOMAIN/fullchain.pem" \
  -subj "/CN=localhost"

echo "### Starting nginx ..."
$COMPOSE up -d nginx

echo "### Deleting dummy certificate for $DOMAIN ..."
docker run --rm -v "$(pwd)/$CERTBOT_CONF:/etc/letsencrypt" certbot/certbot \
  sh -c "rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf"

echo "### Requesting real Let's Encrypt certificate for $DOMAIN ..."
docker run --rm \
  -v "$(pwd)/$CERTBOT_CONF:/etc/letsencrypt" \
  -v "$(pwd)/$CERTBOT_WWW:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email -n

echo "### Reloading nginx ..."
$COMPOSE exec nginx nginx -s reload

echo "Done. Certificate issued for $DOMAIN."
