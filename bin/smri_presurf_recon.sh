#!/bin/bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash smri_presurf_recon.sh <BATCH_DIR> [--submit] [--presurf-only]

Post-segmentation processing:
  6_seg -> 7_presurf -> infant_recon_all

Default validates paths and writes an initial report. Use --submit to submit jobs.
Denoised/questionable outputs must be segmented first and then placed into 6_seg;
there is no supported direct 5_questionable -> recon path.
USAGE
}

if [ "$#" -lt 1 ]; then
    usage
    exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PIPELINE_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
BATCH_DIR=$1
shift
SUBMIT=0
PRESURF_ONLY=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --submit)
            SUBMIT=1
            shift
            ;;
        --Qsubmit)
            echo "--Qsubmit has been disabled. Denoised/questionable outputs must be segmented first; run standard --submit after valid 6_seg exists." >&2
            exit 2
            ;;
        --presurf-only)
            PRESURF_ONLY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ "$BATCH_DIR" != /* ]] && [ -n "${SMRI_DATA_ROOT:-}" ] && [ -d "${SMRI_DATA_ROOT}/${BATCH_DIR}" ]; then
    BATCH_DIR="${SMRI_DATA_ROOT}/${BATCH_DIR}"
fi

if [ ! -d "$BATCH_DIR" ]; then
    echo "Batch directory does not exist: $BATCH_DIR" >&2
    exit 2
fi
BATCH_DIR=$(cd "$BATCH_DIR" && pwd)
PYTHON_BIN="${PYTHON:-python}"
MANIFEST_DIR="${BATCH_DIR}/manifests"

MODE="standard"
SOURCE_DIR="${BATCH_DIR}/6_seg"
TARGET_ROOT="${BATCH_DIR}/7_presurf"
REPORT_PATH="${BATCH_DIR}/logs/postprocessing_report.md"
SUBMITTED_JOBS="${MANIFEST_DIR}/submitted_post_jobs.csv"
PRESURF_SUMMARY="30_presurf_summary.csv"
RECON_SUMMARY="40_recon_summary.csv"

mkdir -p "$MANIFEST_DIR" "$(dirname "$REPORT_PATH")" "${TARGET_ROOT}/logs"

echo "=== sMRI presurf/recon V2 ==="
echo "BATCH_DIR=$BATCH_DIR"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "MODE=$MODE"
echo "SOURCE_DIR=$SOURCE_DIR"
echo "TARGET_ROOT=$TARGET_ROOT"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Missing postprocessing input directory: $SOURCE_DIR" >&2
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/32_write_postprocessing_report_v2.py" --batch-dir "$BATCH_DIR" --report-path "$REPORT_PATH"
    exit 2
fi

if [ "$SUBMIT" -eq 0 ]; then
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/32_write_postprocessing_report_v2.py" --batch-dir "$BATCH_DIR" --report-path "$REPORT_PATH"
    echo "Validation complete. Use --submit to submit presurf/recon jobs."
    exit 0
fi

if ! command -v sbatch >/dev/null 2>&1; then
    echo "sbatch not found. Run this entrypoint on the cluster login node with Slurm available." >&2
    exit 2
fi

PRESURF_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/presurf.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$SOURCE_DIR" "$TARGET_ROOT" "$PRESURF_SUMMARY")
RECON_JOB=""
if [ "$PRESURF_ONLY" -eq 0 ]; then
    RECON_JOB=$(sbatch --parsable --dependency=afterany:${PRESURF_JOB} "${PIPELINE_DIR}/scripts/jobs/recon_all.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$TARGET_ROOT" "$RECON_SUMMARY" "$REPORT_PATH")
fi

{
    echo "mode,source_dir,target_root,presurf_job_id,recon_job_id"
    echo "${MODE},${SOURCE_DIR},${TARGET_ROOT},${PRESURF_JOB},${RECON_JOB}"
} > "$SUBMITTED_JOBS"
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/32_write_postprocessing_report_v2.py" --batch-dir "$BATCH_DIR" --report-path "$REPORT_PATH"

echo "Submitted presurf job: $PRESURF_JOB"
if [ -n "$RECON_JOB" ]; then
    echo "Submitted recon job: $RECON_JOB"
else
    echo "Presurf-only mode: recon not submitted."
fi
echo "Readable report: $REPORT_PATH"
