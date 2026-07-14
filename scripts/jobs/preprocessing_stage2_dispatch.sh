#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_stage2_dispatch
#SBATCH -N 1
#SBATCH -c 1
#SBATCH -t 02:00:00
#SBATCH -o smri_stage2_dispatch_%j.out
#SBATCH -e smri_stage2_dispatch_%j.err

set -u

BATCH_DIR=${1:?Usage: bash preprocessing_stage2_dispatch.sh <BATCH_DIR> <PIPELINE_DIR> [QC_EXCEL] [SUBMIT_DENOISE]}
PIPELINE_DIR=${2:?Usage: bash preprocessing_stage2_dispatch.sh <BATCH_DIR> <PIPELINE_DIR> [QC_EXCEL] [SUBMIT_DENOISE]}
QC_EXCEL=${3:-}
SUBMIT_DENOISE=${4:-1}
PYTHON_BIN="${PYTHON:-python}"
LOG_DIR="${BATCH_DIR}/logs"
MANIFEST_DIR="${BATCH_DIR}/manifests"

mkdir -p "$LOG_DIR" "$MANIFEST_DIR"
exec > >(tee -a "${LOG_DIR}/stage2_dispatch_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/stage2_dispatch_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: stage2 ACPC dispatch ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "QC_EXCEL=$QC_EXCEL"
echo "SUBMIT_DENOISE=$SUBMIT_DENOISE"

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/7_split_for_acpc_v2.py" --batch-dir "$BATCH_DIR" || true

STAGE2_CSV="${MANIFEST_DIR}/stage2_submitted_jobs.csv"
echo "branch,acpc_job_id,qc_job_id" > "$STAGE2_CSV"

QC_JOBS=()
for BRANCH in T1T2 justT1; do
    BRANCH_DIR="${BATCH_DIR}/4_results/${BRANCH}"
    if [ ! -d "$BRANCH_DIR" ]; then
        echo "No ${BRANCH} branch directory; no ACPC job submitted."
        continue
    fi
    COUNT=$(find "$BRANCH_DIR" -mindepth 1 -maxdepth 1 -type d ! -name qc | wc -l)
    if [ "$COUNT" -eq 0 ]; then
        echo "No subjects in ${BRANCH}; no ACPC job submitted."
        continue
    fi
    ACPC_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/acpc_preprocessing.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$BRANCH")
    QC_JOB=$(sbatch --parsable --dependency=afterany:${ACPC_JOB} "${PIPELINE_DIR}/scripts/jobs/qc_acpc_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$BRANCH")
    QC_JOBS+=("$QC_JOB")
    echo "${BRANCH},${ACPC_JOB},${QC_JOB}" >> "$STAGE2_CSV"
    echo "Submitted ${BRANCH} ACPC job ${ACPC_JOB}; QC job ${QC_JOB}"
done

if [ "${#QC_JOBS[@]}" -eq 0 ]; then
    echo "No ACPC QC jobs submitted. Writing report and exiting."
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    exit 0
fi

DEPENDENCY=$(IFS=:; echo "${QC_JOBS[*]}")
QUESTION_JOB=$(sbatch --parsable --dependency=afterany:${DEPENDENCY} "${PIPELINE_DIR}/scripts/jobs/questionable_dispatch.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$QC_EXCEL" "$SUBMIT_DENOISE")
echo "questionable_dispatch,,${QUESTION_JOB}" >> "$STAGE2_CSV"
echo "Submitted questionable dispatch job: $QUESTION_JOB"

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
date
echo "=== stage2 dispatch complete ==="
