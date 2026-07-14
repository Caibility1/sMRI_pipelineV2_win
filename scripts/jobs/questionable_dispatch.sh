#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_questionable
#SBATCH -N 1
#SBATCH -c 1
#SBATCH -t 02:00:00
#SBATCH -o smri_questionable_%j.out
#SBATCH -e smri_questionable_%j.err

set -u

BATCH_DIR=${1:?Usage: bash questionable_dispatch.sh <BATCH_DIR> <PIPELINE_DIR> [QC_EXCEL] [SUBMIT_DENOISE]}
PIPELINE_DIR=${2:?Usage: bash questionable_dispatch.sh <BATCH_DIR> <PIPELINE_DIR> [QC_EXCEL] [SUBMIT_DENOISE]}
QC_EXCEL=${3:-}
SUBMIT_DENOISE=${4:-1}
PYTHON_BIN="${PYTHON:-python}"
LOG_DIR="${BATCH_DIR}/5_questionable/logs"
MANIFEST_DIR="${BATCH_DIR}/manifests"

mkdir -p "$LOG_DIR" "$MANIFEST_DIR"
exec > >(tee -a "${LOG_DIR}/questionable_dispatch_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/questionable_dispatch_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: questionable/fail selection ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "QC_EXCEL=$QC_EXCEL"
echo "SUBMIT_DENOISE=$SUBMIT_DENOISE"

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/8_check_acpc_outputs_v2.py" --batch-dir "$BATCH_DIR" || true
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/9_check_acpc_qc_outputs_v2.py" --batch-dir "$BATCH_DIR" || true

ARGS=(--batch-dir "$BATCH_DIR" --pipeline-dir "$PIPELINE_DIR")
if [ -n "$QC_EXCEL" ]; then
    ARGS+=(--qc-excel "$QC_EXCEL")
fi
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/10_select_denoise_candidates_v2.py" "${ARGS[@]}" || true

SELECTED_COUNT=0
SUMMARY="${MANIFEST_DIR}/20_questionable_summary.csv"
if [ -f "$SUMMARY" ]; then
    SELECTED_COUNT=$(awk -F, '
        NR == 1 {
            for (i = 1; i <= NF; i++) {
                if ($i == "status") status_col = i
            }
            next
        }
        status_col && $status_col == "selected_for_denoise" {count++}
        END {print count+0}
    ' "$SUMMARY")
fi
echo "Selected for denoise: $SELECTED_COUNT"

if [ "$SELECTED_COUNT" -gt 0 ] && [ "$SUBMIT_DENOISE" = "1" ]; then
    DENOISE_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/denoise_moardiff.sh" "$BATCH_DIR" "$PIPELINE_DIR")
    echo "$DENOISE_JOB" > "${MANIFEST_DIR}/denoise_job_id.txt"
    echo "Submitted denoise job: $DENOISE_JOB"
else
    echo "Denoise job not submitted."
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
date
echo "=== questionable/fail dispatch complete ==="
