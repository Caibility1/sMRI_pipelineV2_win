#!/usr/bin/env bash
#SBATCH -p bme_cpu
#SBATCH -J smri_reg2
#SBATCH -N 1
#SBATCH -c 5
#SBATCH -t 2-00:00:00
#SBATCH -o smri_reg2_%j.out
#SBATCH -e smri_reg2_%j.err

set -uo pipefail

BATCH_DIR=${1:?Usage: bash sMRI_pipeline_step0_reg2_v2.sh BATCH_DIR PIPELINE_DIR}
PIPELINE_DIR=${2:?Usage: bash sMRI_pipeline_step0_reg2_v2.sh BATCH_DIR PIPELINE_DIR}
DATA_DIR="${BATCH_DIR}/1_T2toT1/data"
QC_DIR="${BATCH_DIR}/1_T2toT1/qc"
LOG_DIR="${BATCH_DIR}/1_T2toT1/logs"
PYTHON_BIN="${PYTHON:-python}"
REG_SCRIPT="${PIPELINE_DIR}/scripts/jobs/reg2.sh"
REGISTRATION_JOBS="${SLURM_CPUS_PER_TASK:-5}"

mkdir -p "$QC_DIR" "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/reg2_${SLURM_JOB_ID:-local}.out")      2> >(tee -a "${LOG_DIR}/reg2_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: T2-to-T1 registration ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "REGISTRATION_JOBS=$REGISTRATION_JOBS"

if type module >/dev/null 2>&1; then
    module load compiler/gcc/7.3.1 || true
    module load apps/fsl/6.0 || true
fi
export FSLOUTPUTTYPE=NIFTI_GZ
if [ -n "${FSLDIR:-}" ] && [ -f "${FSLDIR}/etc/fslconf/fsl.sh" ]; then
    # shellcheck disable=SC1090
    source "${FSLDIR}/etc/fslconf/fsl.sh"
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py"     --batch-dir "$BATCH_DIR" --input

run_subject() {
    local subject_dir=$1
    local subject
    subject=$(basename "$subject_dir")
    if [ ! -s "${subject_dir}/T2.nii.gz" ]; then
        echo "[$subject] registration skipped: T1-only subject"
        return 0
    fi
    if [ -s "${subject_dir}/registration/T2_to_T1.nii.gz" ] &&        [ -s "${QC_DIR}/${subject}_combined.png" ]; then
        echo "[$subject] registration complete (checkpoint); skipping"
        return 0
    fi
    bash "$REG_SCRIPT" "$subject_dir" "$QC_DIR"
}

if ! [[ "$REGISTRATION_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: REGISTRATION_JOBS must be a positive integer" >&2
    exit 2
fi

running=0
failures=0
for subject_dir in "$DATA_DIR"/*; do
    [ -d "$subject_dir" ] || continue
    run_subject "$subject_dir" &
    running=$((running + 1))
    if [ "$running" -ge "$REGISTRATION_JOBS" ]; then
        if ! wait -n; then failures=$((failures + 1)); fi
        running=$((running - 1))
    fi
done
while [ "$running" -gt 0 ]; do
    if ! wait -n; then failures=$((failures + 1)); fi
    running=$((running - 1))
done

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py"     --batch-dir "$BATCH_DIR" || true
date
echo "=== registration batch complete: failures=$failures ==="
exit "$failures"
