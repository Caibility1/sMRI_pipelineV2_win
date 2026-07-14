#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J smri_recon
#SBATCH -N 1
#SBATCH -n 50
#SBATCH -t 7-00:00:00
#SBATCH -o smri_recon_%j.out
#SBATCH -e smri_recon_%j.err

set -u

BATCH_DIR=${1:?Usage: bash recon_all.sh <BATCH_DIR> <PIPELINE_DIR> [BASE_DIR] [SUMMARY_NAME] [REPORT_PATH]}
PIPELINE_DIR=${2:?Usage: bash recon_all.sh <BATCH_DIR> <PIPELINE_DIR> [BASE_DIR] [SUMMARY_NAME] [REPORT_PATH]}
BASE_DIR="${3:-${BATCH_DIR}/7_presurf}"
SUMMARY_NAME="${4:-40_recon_summary.csv}"
REPORT_PATH="${5:-}"
LOG_DIR="${BASE_DIR}/logs"
PYTHON_BIN="${PYTHON:-python}"
RECON_JOBS="${SMRI_RECON_JOBS:-50}"

mkdir -p "$LOG_DIR" "${BATCH_DIR}/manifests"
exec > >(tee -a "${LOG_DIR}/recon_all_${SLURM_JOB_ID:-local}.out") 2> >(tee -a "${LOG_DIR}/recon_all_${SLURM_JOB_ID:-local}.err" >&2)

echo "=== sMRI Pipeline V2: infant_recon_all ==="
date
echo "BATCH_DIR=$BATCH_DIR"
echo "BASE_DIR=$BASE_DIR"
echo "SUMMARY_NAME=$SUMMARY_NAME"
echo "RECON_JOBS=$RECON_JOBS"

if type module >/dev/null 2>&1; then
    module load tools/parallel/20200122 || true
    module load apps/fsl/6.0 || true
    module load apps/ants || true
fi

export FREESURFER_HOME="${FREESURFER_HOME:-/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/FS8.1}"
export FS_LICENSE="${FS_LICENSE:-/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/license.txt}"
if [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "${FREESURFER_HOME}/SetUpFreeSurfer.sh"
    fs_setup_rc=$?
    set -u
    if [ "$fs_setup_rc" -ne 0 ]; then
        echo "FreeSurfer setup failed: ${FREESURFER_HOME}/SetUpFreeSurfer.sh" >&2
        exit "$fs_setup_rc"
    fi
else
    echo "Missing FreeSurfer setup script: ${FREESURFER_HOME}/SetUpFreeSurfer.sh" >&2
    exit 2
fi

export SUBJECTS_DIR="$BASE_DIR"

recon_complete() {
    local subject_dir="$1"
    [ -f "${subject_dir}/scripts/recon-all.done" ] || \
    [ -f "${subject_dir}/surf/lh.white" ] || \
    [ -f "${subject_dir}/surf/rh.white" ] || \
    [ -f "${subject_dir}/stats/aseg.stats" ]
}

process_subject() {
    local subj=$1
    local age
    local subject_dir="${BASE_DIR}/${subj}"
    local mask_file="${subject_dir}/masked.nii.gz"
    local aseg_file="${subject_dir}/aseg.nii.gz"
    age=$(echo "$subj" | sed -n 's/.*_\([0-9][0-9]*\)mo$/\1/p')

    echo "Processing subject: $subj"
    if [ -z "$age" ]; then
        echo "Missing age suffix for $subj"
        return 0
    fi
    if [ ! -s "$mask_file" ]; then
        echo "Missing masked file: $mask_file"
        return 0
    fi
    if [ ! -s "$aseg_file" ]; then
        echo "Missing aseg file: $aseg_file"
        return 0
    fi
    if recon_complete "$subject_dir"; then
        echo "Completed recon outputs already exist for $subj; skipping."
        return 0
    fi
    if [ -f "${subject_dir}/log/recon.log" ]; then
        mkdir -p "${subject_dir}/log"
        mv "${subject_dir}/log/recon.log" "${subject_dir}/log/recon_$(date +%Y%m%d_%H%M%S).previous.log"
    fi

    if [ "$age" -eq 0 ]; then
        infant_recon_all --s "$subj" \
            --masked "$mask_file" \
            --segfile "$aseg_file" \
            --newborn \
            --keep-going
    else
        infant_recon_all --s "$subj" \
            --masked "$mask_file" \
            --segfile "$aseg_file" \
            --age "$age" \
            --keep-going
    fi

    recon_rc=$?
    if [ "$recon_rc" -ne 0 ]; then
        echo "infant_recon_all failed for $subj with rc=$recon_rc"
        return "$recon_rc"
    fi
    if ! recon_complete "$subject_dir"; then
        echo "infant_recon_all did not create completion markers for $subj"
        return 1
    fi
}

export BASE_DIR
export -f recon_complete
export -f process_subject

SUBJECT_LIST="${LOG_DIR}/recon_subjects_${SLURM_JOB_ID:-local}.txt"
find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d ! -name logs -printf '%f\n' | sort > "$SUBJECT_LIST"

if [ -s "$SUBJECT_LIST" ]; then
    set +e
    parallel --jobs "$RECON_JOBS" --halt never process_subject :::: "$SUBJECT_LIST"
    parallel_rc=$?
    set -e
else
    echo "No subjects found under $BASE_DIR"
    parallel_rc=0
fi

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/31_check_recon_outputs_v2.py" \
    --batch-dir "$BATCH_DIR" \
    --target-root "$BASE_DIR" \
    --summary-name "$SUMMARY_NAME"
if [ -n "$REPORT_PATH" ]; then
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/32_write_postprocessing_report_v2.py" --batch-dir "$BATCH_DIR" --report-path "$REPORT_PATH"
else
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/32_write_postprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
fi
date
echo "=== infant_recon_all batch complete ==="
exit "$parallel_rc"



