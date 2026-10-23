#!/usr/bin/env bash
# Optional fallback for the audited Ubuntu 26.04 WSL environment; no system install.
set -euo pipefail
prefix="$HOME/.local/share/frontiersignal-pg"
if [[ -x "$prefix/usr/lib/postgresql/18/bin/postgres" ]]; then
  printf '%s\n' 'Existing user PostgreSQL binaries preserved.'
  exit 0
fi
packages=(postgresql-18 postgresql-client-18 postgresql-18-pgvector libicu78 libldap2 libpq5 liburing2 libxml2-16 libnuma1)
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
cd "$staging"
apt download "${packages[@]}"
mkdir -p "$prefix"
for package in ./*.deb; do
  dpkg-deb -x "$package" "$prefix"
done
LD_LIBRARY_PATH="$prefix/usr/lib/x86_64-linux-gnu" "$prefix/usr/lib/postgresql/18/bin/postgres" --version
printf '%s\n' 'User binaries ready. Run uv run python scripts/local_postgres.py in the project.'
