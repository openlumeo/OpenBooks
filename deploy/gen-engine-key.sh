#!/bin/sh
# Generates the shared engine key: SHA-256 of 32 random bytes (64 hex chars) and writes it to deploy/.env.engine.
# The same value goes on the inference host and the website VPS as OPENBOOKS_ENGINE_KEY. Never commit the file.
# Usage: sh deploy/gen-engine-key.sh [--force]     then: set -a; . deploy/.env.engine; set +a
set -eu
out="$(dirname "$0")/.env.engine"
if [ -e "$out" ] && [ "${1:-}" != "--force" ]; then
  echo "$out exists; pass --force to replace it (the other host must then get the new key too)" >&2
  exit 1
fi
key=$(head -c 32 /dev/urandom | sha256sum | cut -d' ' -f1)
umask 077
printf 'OPENBOOKS_ENGINE_KEY=%s\n' "$key" > "$out"
echo "wrote $out (OPENBOOKS_ENGINE_KEY, $(printf %s "$key" | wc -c) hex chars)"
