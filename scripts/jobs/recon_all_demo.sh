#!/usr/bin/env bash
set -uo pipefail

BATCH_DIR=${1:?Usage: recon_all_demo.sh BATCH_DIR [RECON_JOBS] [RECON_THREADS]}
RECON_JOBS=${2:-1}
RECON_THREADS=${3:-4}
REQUESTED_SUBJECTS=("${@:4}")
INPUT_ROOT="${BATCH_DIR}/1_T2toT1/data"
RECON_ROOT="${BATCH_DIR}/3_recon"
LOG_DIR="${BATCH_DIR}/logs/recon"
PIPELINE_DIR=${PIPELINE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
PYTHON_BIN=${PYTHON:-python3}

mkdir -p "$RECON_ROOT" "$LOG_DIR" "${BATCH_DIR}/manifests"

if [ -n "${FREESURFER_HOME:-}" ] && [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "${FREESURFER_HOME}/SetUpFreeSurfer.sh"
    set -u
fi
export SUBJECTS_DIR="$RECON_ROOT"
if ! command -v recon-all >/dev/null 2>&1; then
    echo "ERROR: recon-all is not available" >&2
    exit 2
fi
if [ -z "${FS_LICENSE:-}" ] || [ ! -f "$FS_LICENSE" ]; then
    echo "ERROR: FreeSurfer license not found; set FS_LICENSE" >&2
    exit 2
fi
if ! [[ "$RECON_JOBS" =~ ^[1-9][0-9]*$ ]] || ! [[ "$RECON_THREADS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: RECON_JOBS and RECON_THREADS must be positive integers" >&2
    exit 2
fi

ensure_fsaverage() {
    local fsaverage_target="${FREESURFER_HOME}/subjects/fsaverage"
    local fsaverage_link="${SUBJECTS_DIR}/fsaverage"
    local required_label="label/lh.BA1_exvivo.label"
    local current_target

    if [ ! -s "${fsaverage_target}/${required_label}" ]; then
        echo "ERROR: current FreeSurfer fsaverage is incomplete: ${fsaverage_target}" >&2
        return 2
    fi

    if [ -L "$fsaverage_link" ]; then
        current_target=$(readlink "$fsaverage_link")
        if [ "$current_target" != "$fsaverage_target" ]; then
            echo "Repairing stale fsaverage link: ${current_target} -> ${fsaverage_target}"
            rm -f "$fsaverage_link"
        fi
    elif [ -e "$fsaverage_link" ]; then
        if [ ! -s "${fsaverage_link}/${required_label}" ]; then
            echo "ERROR: ${fsaverage_link} exists but is not a compatible fsaverage directory" >&2
            return 2
        fi
        return 0
    fi

    if [ ! -e "$fsaverage_link" ]; then
        ln -s "$fsaverage_target" "$fsaverage_link"
        echo "fsaverage link ready: ${fsaverage_link} -> ${fsaverage_target}"
    fi
    if [ ! -s "${fsaverage_link}/${required_label}" ]; then
        echo "ERROR: failed to prepare a compatible fsaverage link" >&2
        return 2
    fi
}

ensure_fsaverage || exit $?

teaching_outputs_complete() {
    local subject=$1
    [ -s "${SUBJECTS_DIR}/${subject}/scripts/recon-all.done" ] && \
    [ -s "${SUBJECTS_DIR}/${subject}/surf/lh.pial" ] && \
    [ -s "${SUBJECTS_DIR}/${subject}/surf/rh.pial" ] && \
    [ -s "${SUBJECTS_DIR}/${subject}/mri/brainmask.mgz" ] && \
    [ -s "${SUBJECTS_DIR}/${subject}/mri/aseg.mgz" ]
}

recoverable_tail_warning() {
    local subject=$1
    local error_marker="${SUBJECTS_DIR}/${subject}/scripts/recon-all.error"
    local recon_log="${SUBJECTS_DIR}/${subject}/scripts/recon-all.log"
    [ -f "$error_marker" ] && \
    teaching_outputs_complete "$subject" && \
    grep -q "CMD mris_volmask" "$error_marker" && \
    grep -q "Invalid FreeSurfer license key" "$recon_log"
}

run_subject() {
    local input_dir=$1
    local subject
    local t1
    local t2
    local t2_json
    local log
    local rc
    local lock_file
    local lock_host
    local lock_pid
    local current_host
    subject=$(basename "$input_dir")
    t1="${input_dir}/T1.nii.gz"
    t2="${input_dir}/T2.nii.gz"
    t2_json="${input_dir}/T2.json"
    log="${LOG_DIR}/${subject}.log"

    if [ ! -s "$t1" ]; then
        echo "[$subject] FAILED: missing $t1" | tee -a "$log" >&2
        return 1
    fi
    if teaching_outputs_complete "$subject"; then
        if [ ! -f "${SUBJECTS_DIR}/${subject}/scripts/recon-all.error" ]; then
            echo "[$subject] recon-all complete (checkpoint); skipping" | tee -a "$log"
            return 0
        fi
        if recoverable_tail_warning "$subject"; then
            echo "[$subject] WARNING: teaching outputs complete; preserving mris_volmask license tail error" | tee -a "$log"
            return 0
        fi
    fi

    echo "[$subject] recon-all started" | tee -a "$log"
    recon_args=(-s "$subject")
    if [ ! -s "${SUBJECTS_DIR}/${subject}/mri/orig/001.mgz" ]; then recon_args+=(-i "$t1"); fi
    if [ -s "$t2" ] && [ -s "$t2_json" ]; then
        if "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/43_t2_pial_policy_demo.py" "$t2_json" 2>&1 | tee -a "$log"; then
            recon_args+=(-T2 "$t2" -T2pial)
        else
            echo "[$subject] continuing with T1-only recon-all" | tee -a "$log"
        fi
    fi
    lock_file="${SUBJECTS_DIR}/${subject}/scripts/IsRunning.lh+rh"
    if [ -s "$lock_file" ]; then
        lock_host=$(awk '$1 == "HOST" { print $2; exit }' "$lock_file")
        lock_pid=$(awk '$1 == "PROCESSID" { print $2; exit }' "$lock_file")
        current_host=$(hostname)
        if [ "$lock_host" = "$current_host" ] && [[ "$lock_pid" =~ ^[0-9]+$ ]] && kill -0 "$lock_pid" 2>/dev/null; then
            echo "[$subject] FAILED: recon-all is already running as PID $lock_pid" | tee -a "$log" >&2
            return 1
        fi
        echo "[$subject] resuming past stale recon lock from host ${lock_host:-unknown}" | tee -a "$log"
        recon_args+=(-no-isrunning)
    fi
    recon_args+=(-openmp "$RECON_THREADS" -all)
    recon-all "${recon_args[@]}" 2>&1 | tee -a "$log"
    rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 0 ] && \
       [ ! -f "${SUBJECTS_DIR}/${subject}/scripts/recon-all.error" ] && \
       teaching_outputs_complete "$subject"; then
        echo "[$subject] recon-all complete" | tee -a "$log"
    elif recoverable_tail_warning "$subject"; then
        echo "[$subject] WARNING: teaching outputs complete; preserving mris_volmask license tail error" | tee -a "$log"
        rc=0
    else
        [ "$rc" -ne 0 ] || rc=1
        echo "[$subject] FAILED: incomplete recon outputs (rc=$rc)" | tee -a "$log" >&2
    fi
    return "$rc"
}

export INPUT_ROOT SUBJECTS_DIR LOG_DIR PIPELINE_DIR PYTHON_BIN
export -f run_subject

echo "=== Teaching pipeline: standard FreeSurfer recon-all ==="
echo "BATCH_DIR=$BATCH_DIR"
echo "RECON_JOBS=$RECON_JOBS"
echo "RECON_THREADS=$RECON_THREADS"

SUBJECT_DIRS=()
if [ "${#REQUESTED_SUBJECTS[@]}" -gt 0 ]; then
    for subject in "${REQUESTED_SUBJECTS[@]}"; do
        SUBJECT_DIRS+=("${INPUT_ROOT}/${subject}")
    done
else
    mapfile -d '' SUBJECT_DIRS < <(find "$INPUT_ROOT" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
fi
if [ "${#SUBJECT_DIRS[@]}" -eq 0 ]; then
    echo "ERROR: no subject folders found under $INPUT_ROOT" >&2
    exit 2
fi

running=0
failures=0
for input_dir in "${SUBJECT_DIRS[@]}"; do
    run_subject "$input_dir" &
    running=$((running + 1))
    if [ "$running" -ge "$RECON_JOBS" ]; then
        if ! wait -n; then failures=$((failures + 1)); fi
        running=$((running - 1))
    fi
done
while [ "$running" -gt 0 ]; do
    if ! wait -n; then failures=$((failures + 1)); fi
    running=$((running - 1))
done

"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/41_check_standard_recon_demo.py" --batch-dir "$BATCH_DIR" || true
echo "=== recon-all batch complete: failures=$failures ==="
exit "$failures"
