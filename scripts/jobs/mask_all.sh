#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_maskall
#SBATCH -N 1
#SBATCH -c 2
#SBATCH -t 12:00:00
#SBATCH -o smri_maskall_%j.out
#SBATCH -e smri_maskall_%j.err

set -u

BATCH_DIR=${1:?Usage: bash mask_all.sh <BATCH_DIR> <PIPELINE_DIR>}
PIPELINE_DIR=${2:?Usage: bash mask_all.sh <BATCH_DIR> <PIPELINE_DIR>}
LOG_DIR="${BATCH_DIR}/3_skullstrip/logs"
PYTHON_BIN="${PYTHON:-python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

mkdir -p "$LOG_DIR" "${BATCH_DIR}/3_skullstrip/data" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/mask_all_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/mask_all_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: mask_all merge ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "which python: $(command -v "$PYTHON_BIN" || true)"
"$PYTHON_BIN" --version || true
"$PYTHON_BIN" -c "import nibabel, numpy; print('nifti python ok')" || true

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py" --batch-dir "$BATCH_DIR"
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/5_check_nnunet_outputs_v2.py" --batch-dir "$BATCH_DIR"
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/6_mask_all_v2.py" --batch-dir "$BATCH_DIR"

date
echo "=== mask_all job complete ==="
