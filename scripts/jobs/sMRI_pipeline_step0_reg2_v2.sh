#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_reg2
#SBATCH -N 1
#SBATCH -c 5
#SBATCH -t 2-00:00:00
#SBATCH -o smri_reg2_%j.out
#SBATCH -e smri_reg2_%j.err

set -u

BATCH_DIR=${1:?Usage: bash sMRI_pipeline_step0_reg2_v2.sh <BATCH_DIR> <PIPELINE_DIR>}
PIPELINE_DIR=${2:?Usage: bash sMRI_pipeline_step0_reg2_v2.sh <BATCH_DIR> <PIPELINE_DIR>}
DATA_DIR="${BATCH_DIR}/1_T2toT1/data"
QC_DIR="${BATCH_DIR}/1_T2toT1/qc"
LOG_DIR="${BATCH_DIR}/1_T2toT1/logs"
PYTHON_BIN="${PYTHON:-python}"
REG_SCRIPT="${PIPELINE_DIR}/scripts/jobs/reg2.sh"

mkdir -p "$QC_DIR" "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/reg2_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/reg2_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: T2-to-T1 registration batch wrapper ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "DATA_DIR=$DATA_DIR"
echo "QC_DIR=$QC_DIR"
echo "REG_SCRIPT=$REG_SCRIPT"

if type module >/dev/null 2>&1; then
    module load compiler/gcc/7.3.1 || true
    module load tools/parallel/20200122 || true
    module load apps/fsl/6.0 || true
fi

export FSLOUTPUTTYPE=NIFTI_GZ
if [ -n "${FSLDIR:-}" ] && [ -f "${FSLDIR}/etc/fslconf/fsl.sh" ]; then
    # shellcheck disable=SC1090
    source "${FSLDIR}/etc/fslconf/fsl.sh"
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py" --batch-dir "$BATCH_DIR" --input

if command -v parallel >/dev/null 2>&1; then
    find "$DATA_DIR" -mindepth 1 -maxdepth 1 -type d -print | \
    parallel -j "${SLURM_CPUS_PER_TASK:-5}" '
        if [ -s "{}/registration/T2_to_T1.nii.gz" ]; then
            echo "skip existing registration: {}"
        elif [ ! -s "{}/T2.nii.gz" ]; then
            echo "skip T1-only subject: {}"
        else
            bash "'"$REG_SCRIPT"'" "{}" "'"$QC_DIR"'"
        fi
    '
else
    for subject_dir in "$DATA_DIR"/*; do
        [ -d "$subject_dir" ] || continue
        if [ -s "${subject_dir}/registration/T2_to_T1.nii.gz" ]; then
            echo "skip existing registration: $subject_dir"
        elif [ ! -s "${subject_dir}/T2.nii.gz" ]; then
            echo "skip T1-only subject: $subject_dir"
        else
            bash "$REG_SCRIPT" "$subject_dir" "$QC_DIR"
        fi
    done
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py" --batch-dir "$BATCH_DIR"
date
echo "=== registration batch job complete ==="
