#!/bin/bash
#SBATCH -p bme_gpu
#SBATCH -J smri_nnunet523
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --gres=gpu:1
#SBATCH -t 1-00:00:00
#SBATCH -o smri_nnunet523_%j.out
#SBATCH -e smri_nnunet523_%j.err

set -u

BATCH_DIR=${1:?Usage: bash nnunet_task523.sh <BATCH_DIR> <PIPELINE_DIR>}
PIPELINE_DIR=${2:?Usage: bash nnunet_task523.sh <BATCH_DIR> <PIPELINE_DIR>}
CUDA_CHECK_FLAG="${3:-}"
INPUT_DIR="${BATCH_DIR}/2_nnunet_input/imagesTs"
OUTPUT_DIR="${BATCH_DIR}/2_nnunet_output"
LOG_DIR="${OUTPUT_DIR}/logs"
PYTHON_BIN="${PYTHON:-python}"
NNUNET_TASK_NAME="${SMRI_NNUNET_TASK_NAME:-523}"
NNUNET_FOLDS="${SMRI_NNUNET_FOLDS:-}"
NNUNET_DISABLE_TTA="${SMRI_NNUNET_DISABLE_TTA:-0}"
NNUNET_REQUIRE_CUDA="${SMRI_NNUNET_REQUIRE_CUDA:-1}"
NNUNET_CUDA_CHECK_ONLY="${SMRI_NNUNET_CUDA_CHECK_ONLY:-0}"
if [ "$CUDA_CHECK_FLAG" = "--cuda-check-only" ]; then
    NNUNET_CUDA_CHECK_ONLY=1
elif [ -n "$CUDA_CHECK_FLAG" ]; then
    echo "Unknown optional argument: $CUDA_CHECK_FLAG" >&2
    echo "Usage: bash nnunet_task523.sh <BATCH_DIR> <PIPELINE_DIR> [--cuda-check-only]" >&2
    exit 2
fi

if [ -n "${SMRI_NNUNET_CONDA_SH:-}" ] && [ -n "${SMRI_NNUNET_CONDA_ENV:-}" ]; then
    echo "Activating conda env: ${SMRI_NNUNET_CONDA_ENV}"
    set +u
    # shellcheck disable=SC1090
    source "$SMRI_NNUNET_CONDA_SH"
    conda activate "$SMRI_NNUNET_CONDA_ENV"
    set -u
    PYTHON_BIN="${PYTHON:-python}"
elif [ -n "${SMRI_NNUNET_MAMBA_EXE:-}" ] && [ -n "${SMRI_NNUNET_CONDA_ENV:-}" ]; then
    echo "Activating micromamba env: ${SMRI_NNUNET_CONDA_ENV}"
    export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.local/share/mamba}"
    set +u
    eval "$("$SMRI_NNUNET_MAMBA_EXE" shell hook --shell bash)"
    micromamba activate "$SMRI_NNUNET_CONDA_ENV"
    set -u
    PYTHON_BIN="${PYTHON:-python}"
fi

# Prefer the pipeline-local resource tree if present. Slurm exports the submit
# shell environment by default, so stale NNUNET_RESOURCE_DIR/RESULTS_FOLDER
# values from an older source can otherwise silently point at the wrong model.
if [ -n "${SMRI_NNUNET_RESOURCE_DIR:-}" ]; then
    NNUNET_RESOURCE_DIR="${SMRI_NNUNET_RESOURCE_DIR}"
elif [ -d "${PIPELINE_DIR}/resources/models/nnUNet" ]; then
    NNUNET_RESOURCE_DIR="${PIPELINE_DIR}/resources/models/nnUNet"
elif [ -n "${NNUNET_RESOURCE_DIR:-}" ]; then
    NNUNET_RESOURCE_DIR="${NNUNET_RESOURCE_DIR}"
else
    NNUNET_RESOURCE_DIR="${PIPELINE_DIR}/../resources/models/nnUNet"
fi
NNUNET_DATA_DIR="${NNUNET_RESOURCE_DIR}/nnUNetData"
NNUNET_SOURCE_DIR="${NNUNET_SOURCE_DIR:-${NNUNET_RESOURCE_DIR}}"
if [ -d "${NNUNET_SOURCE_DIR}/nnunet" ]; then
    export PYTHONPATH="${NNUNET_SOURCE_DIR}:${PYTHONPATH:-}"
fi

export nnUNet_raw_data_base="${NNUNET_DATA_DIR}/nnUNet_raw_data_base"
export nnUNet_preprocessed="${NNUNET_DATA_DIR}/nnUNet_preprocessed"
export RESULTS_FOLDER="${NNUNET_DATA_DIR}/RESULTS_FOLDER"

mkdir -p "$OUTPUT_DIR" "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/nnunet_task523_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/nnunet_task523_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: nnU-Net Task523 prediction ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "INPUT_DIR=$INPUT_DIR"
echo "OUTPUT_DIR=$OUTPUT_DIR"
echo "NNUNET_RESOURCE_DIR=$NNUNET_RESOURCE_DIR"
echo "NNUNET_SOURCE_DIR=$NNUNET_SOURCE_DIR"
echo "NNUNET_TASK_NAME=$NNUNET_TASK_NAME"
echo "NNUNET_FOLDS=${NNUNET_FOLDS:-auto}"
echo "NNUNET_DISABLE_TTA=$NNUNET_DISABLE_TTA"
echo "NNUNET_REQUIRE_CUDA=$NNUNET_REQUIRE_CUDA"
echo "NNUNET_CUDA_CHECK_ONLY=$NNUNET_CUDA_CHECK_ONLY"
echo "nnUNet_raw_data_base=${nnUNet_raw_data_base:-}"
echo "nnUNet_preprocessed=${nnUNet_preprocessed:-}"
echo "RESULTS_FOLDER=${RESULTS_FOLDER:-}"
echo "which python: $(command -v "$PYTHON_BIN" || true)"
"$PYTHON_BIN" --version || true
"$PYTHON_BIN" -c "import pandas, numpy; print('basic python ok')" || true
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
echo "SLURM_JOB_GPUS=${SLURM_JOB_GPUS:-}"
echo "which nvidia-smi: $(command -v nvidia-smi || true)"
nvidia-smi || true
"$PYTHON_BIN" - <<'PY'
import torch
print("torch =", torch.__version__)
print("torch.version.cuda =", torch.version.cuda)
print("cuda_available =", torch.cuda.is_available())
print("cuda_device_count =", torch.cuda.device_count())
if torch.cuda.is_available():
    print("cuda_device_name =", torch.cuda.get_device_name(0))
PY
echo "which nnUNet_predict: $(command -v nnUNet_predict || true)"
if command -v nnUNet_predict >/dev/null 2>&1; then
    NNUNET_PREDICT_MODE="entrypoint"
    nnUNet_predict --help | head -40 || true
elif "$PYTHON_BIN" -c "import nnunet.inference.predict_simple; print('nnU-Net source import ok')" >/dev/null 2>&1; then
    NNUNET_PREDICT_MODE="module"
    "$PYTHON_BIN" -m nnunet.inference.predict_simple --help | head -40 || true
else
    NNUNET_PREDICT_MODE="missing"
fi
echo "NNUNET_PREDICT_MODE=$NNUNET_PREDICT_MODE"

if [ ! -d "$INPUT_DIR" ]; then
    echo "Missing nnU-Net input directory: $INPUT_DIR" >&2
    exit 2
fi

if [ "$NNUNET_REQUIRE_CUDA" = "1" ]; then
    if ! "$PYTHON_BIN" -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)"; then
        echo "CUDA is not available to PyTorch. Refusing to run nnU-Net on CPU because it is extremely slow." >&2
        echo "Check GPU allocation (--gres=gpu:1), CUDA-enabled PyTorch, and CUDA_VISIBLE_DEVICES." >&2
        echo "Set NNUNET_REQUIRE_CUDA=0 only if you intentionally want a CPU test." >&2
        exit 2
    fi
fi

if [ "$NNUNET_CUDA_CHECK_ONLY" = "1" ]; then
    echo "CUDA check only requested; exiting before nnUNet_predict."
    date
    echo "=== nnU-Net CUDA check complete ==="
    exit 0
fi

if "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/5_check_nnunet_outputs_v2.py" --batch-dir "$BATCH_DIR" --require-all; then
    echo "All expected nnU-Net masks already exist. Skipping nnUNet_predict."
    date
    echo "=== nnU-Net job complete ==="
    exit 0
fi

if [ "$NNUNET_PREDICT_MODE" = "missing" ]; then
    echo "nnU-Net predictor not found. Install nnunet or set NNUNET_SOURCE_DIR to the nnU-Net v1 source tree." >&2
    echo "Diagnostics:" >&2
    echo "  PYTHON_BIN=$PYTHON_BIN" >&2
    echo "  PYTHONPATH=${PYTHONPATH:-}" >&2
    echo "  NNUNET_RESOURCE_DIR=$NNUNET_RESOURCE_DIR" >&2
    echo "  NNUNET_SOURCE_DIR=$NNUNET_SOURCE_DIR" >&2
    echo "  Expected source package: ${NNUNET_SOURCE_DIR}/nnunet" >&2
    ls -la "$NNUNET_RESOURCE_DIR" >&2 || true
    exit 2
fi

TASK_MODEL_DIR="${RESULTS_FOLDER}/nnUNet/3d_fullres/Task523_CBCPSkullStrip"
if [ ! -d "$TASK_MODEL_DIR" ]; then
    echo "Missing Task523 trained model under RESULTS_FOLDER: $TASK_MODEL_DIR" >&2
    echo "Visible 3d_fullres model directories:" >&2
    find "${RESULTS_FOLDER}/nnUNet/3d_fullres" -maxdepth 2 -type d 2>/dev/null | sort >&2 || true
    echo "If your Task523 folder has a different name, set NNUNET_TASK_NAME to that full task name before submitting." >&2
    exit 2
fi

if [ "$NNUNET_PREDICT_MODE" = "entrypoint" ]; then
    CMD=(nnUNet_predict \
        -i "$INPUT_DIR" \
        -o "$OUTPUT_DIR" \
        -m 3d_fullres \
        -t "$NNUNET_TASK_NAME")
else
    CMD=("$PYTHON_BIN" -m nnunet.inference.predict_simple \
        -i "$INPUT_DIR" \
        -o "$OUTPUT_DIR" \
        -m 3d_fullres \
        -t "$NNUNET_TASK_NAME")
fi
if [ -n "$NNUNET_FOLDS" ]; then
    CMD+=(-f "$NNUNET_FOLDS")
fi
if [ "$NNUNET_DISABLE_TTA" = "1" ]; then
    CMD+=(--disable_tta)
fi
echo "Running: ${CMD[*]}"
"${CMD[@]}"

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/5_check_nnunet_outputs_v2.py" --batch-dir "$BATCH_DIR"
date
echo "=== nnU-Net job complete ==="
