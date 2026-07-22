#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: smri_reconstruction_demo.sh BATCH_DIR [options]

Stages: DICOM conversion -> standard FreeSurfer recon-all

Options:
  --submit                 Accepted for compatibility; execution is synchronous.
  --skip-dicom             Use existing 1_T2toT1/data/<ID>/T1.nii.gz inputs.
  --dcm2niix-only          Convert every DICOM series, write inventory, then stop for QC.
  --convert-only           Alias for --dcm2niix-only.
  --select-only            Copy selected T1/T2 into data/<ID>, then stop before recon.
  --raw-dir PATH           DICOM root relative to BATCH_DIR (default: 0_rawdata).
  --recon-jobs N           Subjects reconstructed concurrently (default: 1).
  --recon-threads N        CPU threads used by each recon (default: 4).
  --subject ID             Convert only this subject; repeatable.
  --t1-series NUMBER       Resolve one subject's ambiguous T1 series.
  --t2-series NUMBER       Resolve one subject's ambiguous T2 series.
  --force-convert          Replace standardized T1/T2 files from DICOM.
  -h, --help               Show this help.
EOF
}

if [ "$#" -eq 0 ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

BATCH_DIR=$1
shift
PIPELINE_DIR=${PIPELINE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
PYTHON_BIN=${PYTHON:-python3}
RECON_JOBS=1
RECON_THREADS=4
SKIP_DICOM=0
CONVERT_ONLY=0
SELECT_ONLY=0
DICOM_ARGS=()
RECON_SUBJECTS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --submit) ;;
        --skip-dicom) SKIP_DICOM=1 ;;
        --dcm2niix-only|--convert-only) CONVERT_ONLY=1; DICOM_ARGS+=("--inventory-only") ;;
        --select-only) SELECT_ONLY=1 ;;
        --force-convert) DICOM_ARGS+=("--force") ;;
        --recon-jobs)
            [ "$#" -ge 2 ] || { echo "ERROR: --recon-jobs needs a value" >&2; exit 2; }
            RECON_JOBS=$2
            shift
            ;;
        --recon-threads)
            [ "$#" -ge 2 ] || { echo "ERROR: --recon-threads needs a value" >&2; exit 2; }
            RECON_THREADS=$2
            shift
            ;;
        --subject)
            [ "$#" -ge 2 ] || { echo "ERROR: --subject needs a value" >&2; exit 2; }
            DICOM_ARGS+=("--subject" "$2")
            RECON_SUBJECTS+=("$2")
            shift
            ;;
        --t1-series|--t2-series|--raw-dir)
            [ "$#" -ge 2 ] || { echo "ERROR: $1 needs a value" >&2; exit 2; }
            DICOM_ARGS+=("$1" "$2")
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

mkdir -p "${BATCH_DIR}/manifests" "${BATCH_DIR}/logs"
echo "=== sMRI teaching reconstruction ==="
echo "BATCH_DIR=$BATCH_DIR"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "RECON_JOBS=$RECON_JOBS"
echo "RECON_THREADS=$RECON_THREADS"

if [ "$SKIP_DICOM" -eq 0 ]; then
    echo "[1/2] DICOM conversion started"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/40_dicom_to_nifti_demo.py" \
        --batch-dir "$BATCH_DIR" "${DICOM_ARGS[@]}"
    echo "[1/2] DICOM conversion complete"
else
    echo "[1/2] DICOM conversion skipped by --skip-dicom"
fi

if [ "$CONVERT_ONLY" -eq 1 ]; then
    echo "Stopped after DICOM conversion as requested."
    echo "Review ${BATCH_DIR}/manifests/00_dicom_series_inventory.csv before reconstruction."
    exit 0
fi

if [ "$SELECT_ONLY" -eq 1 ]; then
    echo "Selected T1/T2 standardization complete."
    echo "Review ${BATCH_DIR}/1_T2toT1/data before reconstruction."
    exit 0
fi
echo "[2/2] Standard FreeSurfer recon-all started"
bash "${PIPELINE_DIR}/scripts/jobs/recon_all_demo.sh" "$BATCH_DIR" "$RECON_JOBS" "$RECON_THREADS" "${RECON_SUBJECTS[@]}"
echo "[2/2] Standard FreeSurfer recon-all complete"
echo "=== reconstruction pipeline complete ==="
