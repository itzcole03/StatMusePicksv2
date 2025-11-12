#!/usr/bin/env bash
set -euo pipefail

# install_env.sh
# Idempotent installer for /etc/statmuse/env using the repo template
# Usage:
#   sudo ./scripts/systemd/install_env.sh [--repo-root /srv/statmusepicks] [--audit-dir /var/lib/statmuse/ingest_audit] [--webhook https://...] [--hmac SECRET] [--service-user statmuse]

REPO_ROOT_DEFAULT="/srv/statmusepicks"
AUDIT_DIR_DEFAULT="/var/lib/statmuse/ingest_audit"
WEBHOOK_DEFAULT=""
HMAC_DEFAULT=""
SERVICE_USER_DEFAULT="statmuse"

DEST_DIR=/etc/statmuse
DEST_FILE="$DEST_DIR/env"
TEMPLATE_FILE="$(cd "$(dirname "$0")" && pwd)/env.example"

usage() {
  cat <<EOF
Usage: sudo $0 [options]

Options:
  --repo-root PATH       Absolute path for REPO_ROOT (default: $REPO_ROOT_DEFAULT)
  --audit-dir PATH       INGEST_AUDIT_DIR (default: $AUDIT_DIR_DEFAULT)
  --webhook URL          INGEST_ALERT_WEBHOOK (optional)
  --hmac SECRET          INGEST_ALERT_HMAC_SECRET (optional)
  --service-user NAME    SERVICE_USER (default: $SERVICE_USER_DEFAULT)
  -h, --help             Show this help

Example:
  sudo $0 --repo-root /srv/statmusepicks --hmac "$(openssl rand -hex 32)"
EOF
}

ARGS_REPO_ROOT="${REPO_ROOT_DEFAULT}"
ARGS_AUDIT_DIR="${AUDIT_DIR_DEFAULT}"
ARGS_WEBHOOK="${WEBHOOK_DEFAULT}"
ARGS_HMAC="${HMAC_DEFAULT}"
ARGS_SERVICE_USER="${SERVICE_USER_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      ARGS_REPO_ROOT="$2"; shift 2;;
    --audit-dir)
      ARGS_AUDIT_DIR="$2"; shift 2;;
    --webhook)
      ARGS_WEBHOOK="$2"; shift 2;;
    --hmac)
      ARGS_HMAC="$2"; shift 2;;
    --service-user)
      ARGS_SERVICE_USER="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo)" >&2
  exit 3
fi

mkdir -p "$DEST_DIR"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "Template file not found: $TEMPLATE_FILE" >&2
  exit 4
fi

# Build the file content from template, replacing placeholders when present
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

awk -v repo="$ARGS_REPO_ROOT" -v audit="$ARGS_AUDIT_DIR" -v webhook="$ARGS_WEBHOOK" -v hmac="$ARGS_HMAC" -v svc="$ARGS_SERVICE_USER" '
  { gsub(/REPO_ROOT=\/srv\/statmusepicks/, "REPO_ROOT=" repo); gsub(/INGEST_AUDIT_DIR=\/var\/lib\/statmuse\/ingest_audit/, "INGEST_AUDIT_DIR=" audit); gsub(/INGEST_ALERT_WEBHOOK=.+/, "INGEST_ALERT_WEBHOOK=" webhook); gsub(/INGEST_ALERT_HMAC_SECRET=.+/, "INGEST_ALERT_HMAC_SECRET=" hmac); gsub(/SERVICE_USER=.+/, "SERVICE_USER=" svc); print }
' "$TEMPLATE_FILE" > "$tmpfile"

# If webhook or hmac were intentionally left empty, remove trailing placeholders
sed -i "s/INGEST_ALERT_WEBHOOK=\s*$/INGEST_ALERT_WEBHOOK=/" "$tmpfile" || true
sed -i "s/INGEST_ALERT_HMAC_SECRET=\s*$/INGEST_ALERT_HMAC_SECRET=/" "$tmpfile" || true

# Write final file (atomic)
cp "$tmpfile" "$DEST_FILE"
chown root:root "$DEST_FILE"
chmod 600 "$DEST_FILE"

echo "Installed environment file at $DEST_FILE (owner=root, mode=600)."
echo "Please set 'User' in the systemd unit to the intended service account (e.g. $ARGS_SERVICE_USER)."

exit 0
