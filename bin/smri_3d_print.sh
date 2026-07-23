#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PIPELINE_DIR="$repo_root"
export PYTHON=${PYTHON:-python3}

if [ "$#" -eq 0 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: ./bin/smri_3d_print.sh BATCH_DIR [--subject ID] [--force]"
    exit 0
fi

exec bash "${repo_root}/scripts/jobs/export_stl_demo.sh" "$@"
