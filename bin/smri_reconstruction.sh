#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PIPELINE_DIR="$repo_root"
export PYTHON=${PYTHON:-python3}

exec bash "${repo_root}/scripts/jobs/smri_reconstruction_demo.sh" "$@"
