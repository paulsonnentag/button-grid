#!/usr/bin/env bash
# Run a command with KiCad 9 available. Uses a local kicad-cli if present,
# otherwise the official KiCad docker image (repo mounted at /w).
#   hardware/scripts/kicad.sh kicad-cli version
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${KICAD_IMAGE:-kicad/kicad:9.0}"

# make sure the standard symbol/footprint library tables exist (fresh $HOME in CI/docker)
SETUP='cfg="$HOME/.config/kicad/9.0"; mkdir -p "$cfg";
for t in sym-lib-table fp-lib-table; do
  [ -f "$cfg/$t" ] || cp /usr/share/kicad/template/$t "$cfg/$t" 2>/dev/null || true
done; exec "$@"'

if [ -n "${IN_KICAD_CONTAINER:-}" ] || { command -v kicad-cli >/dev/null 2>&1 && [ -z "${FORCE_DOCKER:-}" ]; }; then
  cd "$REPO" && exec bash -c "$SETUP" _ "$@"
fi
exec docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e IN_KICAD_CONTAINER=1 \
  -v "$REPO":/w -w /w "$IMAGE" bash -c "$SETUP" _ "$@"
