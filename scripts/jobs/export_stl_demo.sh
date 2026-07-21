#!/usr/bin/env bash
set -euo pipefail

BATCH_DIR=${1:?Usage: export_stl_demo.sh BATCH_DIR [additional exporter arguments]}
shift
PIPELINE_DIR=${PIPELINE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
PYTHON_BIN=${PYTHON:-python3}

if [ -n "${FREESURFER_HOME:-}" ] && [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "${FREESURFER_HOME}/SetUpFreeSurfer.sh" || true
    set -u
fi
if ! command -v mris_convert >/dev/null 2>&1; then
    echo "ERROR: mris_convert is not available" >&2
    exit 2
fi

exec "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/42_export_pial_stl_demo.py" \
    --batch-dir "$BATCH_DIR" "$@"
