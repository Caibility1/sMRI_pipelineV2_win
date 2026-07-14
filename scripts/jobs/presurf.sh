#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_presurf
#SBATCH -N 1
#SBATCH -c 4
#SBATCH -t 12:00:00
#SBATCH -o smri_presurf_%j.out
#SBATCH -e smri_presurf_%j.err

set -u

BATCH_DIR=${1:?Usage: bash presurf.sh <BATCH_DIR> <PIPELINE_DIR> [SOURCE_DIR] [TARGET_ROOT] [SUMMARY_NAME]}
PIPELINE_DIR=${2:?Usage: bash presurf.sh <BATCH_DIR> <PIPELINE_DIR> [SOURCE_DIR] [TARGET_ROOT] [SUMMARY_NAME]}
SOURCE_DIR="${3:-${BATCH_DIR}/6_seg}"
TARGET_ROOT="${4:-${BATCH_DIR}/7_presurf}"
SUMMARY_NAME="${5:-30_presurf_summary.csv}"
PYTHON_BIN="${PYTHON:-python}"
LOG_DIR="${TARGET_ROOT}/logs"

mkdir -p "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/presurf_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/presurf_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: presurf ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "SOURCE_DIR=$SOURCE_DIR"
echo "TARGET_ROOT=$TARGET_ROOT"
echo "SUMMARY_NAME=$SUMMARY_NAME"
echo "which python: $(command -v "$PYTHON_BIN" || true)"
"$PYTHON_BIN" --version || true
"$PYTHON_BIN" -c "import SimpleITK, numpy; print('presurf python ok')" || true

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/30_presurf_v2.py" \
    --batch-dir "$BATCH_DIR" \
    --source-dir "$SOURCE_DIR" \
    --target-root "$TARGET_ROOT" \
    --summary-name "$SUMMARY_NAME"

date
echo "=== presurf complete ==="
