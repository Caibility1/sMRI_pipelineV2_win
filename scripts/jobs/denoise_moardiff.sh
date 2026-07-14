#!/bin/bash
#SBATCH -p bme_gpu
#SBATCH -J smri_denoise
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH -N 1
#SBATCH -t 2-00:00:00
#SBATCH -o smri_denoise_%j.out
#SBATCH -e smri_denoise_%j.err

set -u

BATCH_DIR=${1:?Usage: bash denoise_moardiff.sh <BATCH_DIR> <PIPELINE_DIR>}
PIPELINE_DIR=${2:?Usage: bash denoise_moardiff.sh <BATCH_DIR> <PIPELINE_DIR>}
PYTHON_BIN="${PYTHON:-python}"
LOG_DIR="${BATCH_DIR}/5_questionable/logs"
MANIFEST_DIR="${BATCH_DIR}/manifests"
INPUT_DIR="${BATCH_DIR}/5_questionable/input"
OUTPUT_DIR="${BATCH_DIR}/5_questionable/output"
FINAL_DIR="${BATCH_DIR}/5_questionable/final"
if [ -n "${SMRI_MOARDIFF_DIR:-}" ]; then
    MOARDIFF_DIR="${SMRI_MOARDIFF_DIR}"
elif [ -n "${MOARDIFF_DIR:-}" ] && [ -f "${MOARDIFF_DIR}/main.py" ]; then
    MOARDIFF_DIR="${MOARDIFF_DIR}"
elif [ -f "${PIPELINE_DIR}/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune/main.py" ]; then
    MOARDIFF_DIR="${PIPELINE_DIR}/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune"
elif [ -f "${PIPELINE_DIR}/resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune/main.py" ]; then
    MOARDIFF_DIR="${PIPELINE_DIR}/resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune"
else
    MOARDIFF_DIR="/public_bme2/bme-zhanghan/linmo2025/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune"
fi
if [ -z "${MOARDIFF_CKPT:-}" ] || [ ! -f "${MOARDIFF_CKPT:-}" ]; then
    MOARDIFF_CKPT="${MOARDIFF_DIR}/exp/logs/finetuneDPM_with_age/ckpt_100000.pth"
fi
MOARDIFF_CONFIG_NAME="${MOARDIFF_CONFIG_NAME:-inference.yml}"
SMRI_CONTAINER_ENGINE="${SMRI_CONTAINER_ENGINE:-singularity}"

mkdir -p "$LOG_DIR" "$OUTPUT_DIR" "$FINAL_DIR" "$MANIFEST_DIR"
exec > >(tee -a "${LOG_DIR}/denoise_moardiff_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/denoise_moardiff_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: moAR-diff denoise ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "INPUT_DIR=$INPUT_DIR"
echo "OUTPUT_DIR=$OUTPUT_DIR"
echo "FINAL_DIR=$FINAL_DIR"
echo "MOARDIFF_DIR=$MOARDIFF_DIR"
echo "MOARDIFF_CKPT=$MOARDIFF_CKPT"
echo "MOARDIFF_CONFIG_NAME=$MOARDIFF_CONFIG_NAME"
echo "which python: $(command -v "$PYTHON_BIN" || true)"

if [ -n "${SMRI_DENOISE_CONDA_SH:-}" ] && [ -n "${SMRI_DENOISE_CONDA_ENV:-}" ]; then
    if [ -f "$SMRI_DENOISE_CONDA_SH" ]; then
        echo "Activating conda env: ${SMRI_DENOISE_CONDA_ENV}"
        set +u
        # shellcheck disable=SC1090
        source "$SMRI_DENOISE_CONDA_SH"
        conda activate "$SMRI_DENOISE_CONDA_ENV"
        set -u
    else
        echo "WARN: SMRI_DENOISE_CONDA_SH not found: ${SMRI_DENOISE_CONDA_SH}; using current python" >&2
    fi
elif [ -n "${SMRI_DENOISE_MAMBA_EXE:-}" ] && [ -n "${SMRI_DENOISE_CONDA_ENV:-}" ]; then
    echo "Activating micromamba env: ${SMRI_DENOISE_CONDA_ENV}"
    export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.local/share/mamba}"
    set +u
    eval "$("$SMRI_DENOISE_MAMBA_EXE" shell hook --shell bash)"
    micromamba activate "$SMRI_DENOISE_CONDA_ENV"
    set -u
fi

WRAPPER="${PIPELINE_DIR}/scripts/steps/21_run_moardiff_denoise_v2.py"
if [ -n "${SMRI_DENOISE_CONTAINER:-}" ]; then
    echo "Running in Singularity/Apptainer container: ${SMRI_DENOISE_CONTAINER}"
    "$SMRI_CONTAINER_ENGINE" exec --nv ${SMRI_DENOISE_BIND_ARGS:-} "$SMRI_DENOISE_CONTAINER" "$PYTHON_BIN" "$WRAPPER" \
        --batch-dir "$BATCH_DIR" \
        --pipeline-dir "$PIPELINE_DIR" \
        --moardiff-dir "$MOARDIFF_DIR" \
        --checkpoint "$MOARDIFF_CKPT" \
        --config-name "$MOARDIFF_CONFIG_NAME" \
        --run-id "${SLURM_JOB_ID:-local}"
    STATUS=$?
else
    "$PYTHON_BIN" --version || true
    "$PYTHON_BIN" "$WRAPPER" \
        --batch-dir "$BATCH_DIR" \
        --pipeline-dir "$PIPELINE_DIR" \
        --moardiff-dir "$MOARDIFF_DIR" \
        --checkpoint "$MOARDIFF_CKPT" \
        --config-name "$MOARDIFF_CONFIG_NAME" \
        --run-id "${SLURM_JOB_ID:-local}"
    STATUS=$?
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
exit "$STATUS"
