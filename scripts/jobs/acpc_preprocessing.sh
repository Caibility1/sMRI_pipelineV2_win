#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_acpc
#SBATCH -N 1
#SBATCH -n 20
#SBATCH -t 1-00:00:00
#SBATCH -o smri_acpc_%j.out
#SBATCH -e smri_acpc_%j.err

set -u

BATCH_DIR=${1:?Usage: bash acpc_preprocessing.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
PIPELINE_DIR=${2:?Usage: bash acpc_preprocessing.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
BRANCH=${3:?Usage: bash acpc_preprocessing.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
INPUT_DIR="${BATCH_DIR}/4_results/${BRANCH}"
LOG_DIR="${BATCH_DIR}/4_results/logs"
PYTHON_BIN="${PYTHON:-python}"
PREPROCESS_SCRIPT="${SMRI_ACPC_SCRIPT:-${PIPELINE_DIR}/scripts/legacy/preprocessing_ttl_v1.sh}"
if [ -n "${SMRI_TEMPLATE_DIR:-}" ]; then
    TEMPLATE_DIR="$SMRI_TEMPLATE_DIR"
elif [ -d "${PIPELINE_DIR}/resources/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0" ]; then
    TEMPLATE_DIR="${PIPELINE_DIR}/resources/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0"
else
    TEMPLATE_DIR="/public_bme/data/zhanghan_group/sMRI_pipeline_new/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0/"
fi
ACPC_JOBS="${SMRI_ACPC_JOBS:-20}"

mkdir -p "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/acpc_${BRANCH}_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/acpc_${BRANCH}_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: ACPC ${BRANCH} ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "INPUT_DIR=$INPUT_DIR"
echo "PREPROCESS_SCRIPT=$PREPROCESS_SCRIPT"
echo "TEMPLATE_DIR=$TEMPLATE_DIR"
echo "ACPC_JOBS=$ACPC_JOBS"

if type module >/dev/null 2>&1; then
    module load compiler/gcc/7.3.1 || true
    module load tools/parallel/20200122 || true
    module load apps/fsl/6.0 || true
    module load apps/ants || true
fi

export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"
if [ -n "${FSLDIR:-}" ] && [ -f "${FSLDIR}/etc/fslconf/fsl.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "${FSLDIR}/etc/fslconf/fsl.sh"
    set -u
    export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"
else
    echo "WARN: FSLDIR/fsl.sh not available after module load; FSL commands may fail." >&2
fi
if [ -d "${PIPELINE_DIR}/resources/wsl_shims" ]; then
    export SMRI_FSL_AFF2RIGID_ORIGINAL="${FSLDIR:-}/bin/aff2rigid"
    chmod +x "${PIPELINE_DIR}/resources/wsl_shims/aff2rigid" 2>/dev/null || true
    export PATH="${PIPELINE_DIR}/resources/wsl_shims:${PATH}"
fi

echo "FSLDIR=${FSLDIR:-UNSET}"
echo "FSLOUTPUTTYPE=${FSLOUTPUTTYPE:-UNSET}"
which robustfov || true
which aff2rigid || true
which applywarp || true
which N4BiasFieldCorrection || true

SMRI_ACPC_SOURCE_FREESURFER="${SMRI_ACPC_SOURCE_FREESURFER:-0}"
if [ "$SMRI_ACPC_SOURCE_FREESURFER" = "1" ]; then
    export FREESURFER_HOME="${SMRI_ACPC_FREESURFER_HOME:-${FREESURFER_HOME:-/public/software/apps/freesurfer_infant/freesurfer/}}"
    if [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
        echo "Sourcing FreeSurfer for ACPC: ${FREESURFER_HOME}"
        set +u
        # shellcheck disable=SC1090
        source "${FREESURFER_HOME}/SetUpFreeSurfer.sh"
        set -u
    else
        echo "FreeSurfer setup not found for ACPC: ${FREESURFER_HOME}"
    fi
else
    echo "Skipping FreeSurfer setup for ACPC; preprocessing_ttl_v1.sh uses FSL/ANTs only."
fi
if [ -n "${SMRI_WORKBENCH_BIN:-}" ]; then
    export PATH="$PATH:$SMRI_WORKBENCH_BIN"
elif [ -d "${PIPELINE_DIR}/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64" ]; then
    export PATH="$PATH:${PIPELINE_DIR}/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
else
    export PATH="$PATH:/public_bme/home/zhanghan_group_public/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
fi

if [ ! -d "$INPUT_DIR" ]; then
    echo "Input branch does not exist; skipping: $INPUT_DIR"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/8_check_acpc_outputs_v2.py" --batch-dir "$BATCH_DIR" --branch "$BRANCH"
    exit 0
fi

SUBJECT_LIST="${LOG_DIR}/acpc_${BRANCH}_${SLURM_JOB_ID:-local}_subjects.txt"
: > "$SUBJECT_LIST"
for subject_dir in "$INPUT_DIR"/*; do
    [ -d "$subject_dir" ] || continue
    [ "$(basename "$subject_dir")" = "qc" ] && continue
    if [ -s "${subject_dir}/T1_acpc.nii.gz" ]; then
        if [ "$BRANCH" = "justT1" ] || [ -s "${subject_dir}/T2_acpc.nii.gz" ]; then
            echo "skip existing ACPC: $subject_dir"
            continue
        fi
    fi
    echo "$subject_dir" >> "$SUBJECT_LIST"
done

if [ -s "$SUBJECT_LIST" ]; then
    parallel -j "$ACPC_JOBS" bash "$PREPROCESS_SCRIPT" {} "$TEMPLATE_DIR" :::: "$SUBJECT_LIST"
else
    echo "No ACPC subjects need processing for ${BRANCH}."
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/8_check_acpc_outputs_v2.py" --batch-dir "$BATCH_DIR" --branch "$BRANCH"

date
echo "=== ACPC ${BRANCH} complete ==="
