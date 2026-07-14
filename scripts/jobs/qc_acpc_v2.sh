#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_qc_acpc
#SBATCH -N 1
#SBATCH -n 5
#SBATCH -t 1-00:00:00
#SBATCH -o smri_qc_acpc_%j.out
#SBATCH -e smri_qc_acpc_%j.err

set -u

BATCH_DIR=${1:?Usage: bash qc_acpc_v2.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
PIPELINE_DIR=${2:?Usage: bash qc_acpc_v2.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
BRANCH=${3:?Usage: bash qc_acpc_v2.sh <BATCH_DIR> <PIPELINE_DIR> <T1T2|justT1>}
SOURCE_DIR="${BATCH_DIR}/4_results/${BRANCH}"
QC_DIR="${SOURCE_DIR}/qc"
LOG_DIR="${BATCH_DIR}/4_results/logs"
PYTHON_BIN="${PYTHON:-python}"

mkdir -p "$QC_DIR" "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/qc_acpc_${BRANCH}_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/qc_acpc_${BRANCH}_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: ACPC QC ${BRANCH} ==="
date
echo "SOURCE_DIR=$SOURCE_DIR"
echo "QC_DIR=$QC_DIR"

module load compiler/gcc/7.3.1
module load tools/parallel/20200122
module load apps/fsl/6.0

export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"
if [ -n "${FSLDIR:-}" ] && [ -f "${FSLDIR}/etc/fslconf/fsl.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "${FSLDIR}/etc/fslconf/fsl.sh"
    set -u
    export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"
else
    echo "WARN: FSLDIR/fsl.sh not available after module load; slicer may fail." >&2
fi
echo "FSLDIR=${FSLDIR:-UNSET}"
echo "FSLOUTPUTTYPE=${FSLOUTPUTTYPE:-UNSET}"
which slicer || true

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Source branch does not exist; skipping: $SOURCE_DIR"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/9_check_acpc_qc_outputs_v2.py" --batch-dir "$BATCH_DIR" --branch "$BRANCH"
    exit 0
fi

for subject_dir in "$SOURCE_DIR"/*; do
    [ -d "$subject_dir" ] || continue
    subject_name=$(basename "$subject_dir")
    [ "$subject_name" = "qc" ] && continue
    png_name=$(echo "$subject_name" | sed 's/_[0-9][0-9]*mo$//')
    if [ -f "${subject_dir}/T1_acpc.nii.gz" ]; then
        slicer "${subject_dir}/T1_acpc.nii.gz" -x 0.5 "${QC_DIR}/${png_name}.png"
        echo "Created QC image for ${subject_name}"
    else
        echo "Warning: T1_acpc.nii.gz not found for ${subject_name}"
    fi
done

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/9_check_acpc_qc_outputs_v2.py" --batch-dir "$BATCH_DIR" --branch "$BRANCH"

date
echo "=== ACPC QC ${BRANCH} complete ==="
