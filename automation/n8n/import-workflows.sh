#!/bin/sh
set -eu

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml -f docker-compose.automation.yml \
  --profile automation exec -T n8n \
  n8n import:workflow --separate --input=/opt/hr-ats-workflows
