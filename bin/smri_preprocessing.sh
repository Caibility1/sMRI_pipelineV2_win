#!/bin/bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  bash smri_preprocessing.sh <BATCH_DIR> [--qc-excel <xlsx>] [--dry-run] [--submit] [--stage1-only] [--no-denoise-submit]
  bash smri_preprocessing.sh <BATCH_DIR> --acpc-start [--qc-excel <xlsx>] [--no-denoise-submit]
  bash smri_preprocessing.sh <BATCH_DIR> --denoising-start [--qc-excel <xlsx>] [--no-denoise-submit]
  bash smri_preprocessing.sh <BATCH_DIR> --denoising [--no-denoise-submit]

Current implemented flow:
  default              Run lightweight intake steps locally only.
  --submit             Run lightweight steps locally, submit heavy Slurm jobs with
                       dependencies, run split/selection locally, then submit denoise.
                       mask_all defaults to Slurm; a local fallback is kept inline.
  --stage1-only        With --submit, stop after mask_all.
  --no-denoise-submit  Select questionable/fail subjects but do not submit denoise.
  --acpc-start         Resume at ACPC. If 4_results is missing/empty, rebuild it from 3_skullstrip first.
  --denoising-start    Resume at local Fail/Questionable selection, then submit denoise.
  --denoising          Submit denoise from existing 5_questionable/input, then write report.
USAGE
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PIPELINE_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)

if [ -n "${SLURM_JOB_ID:-}" ] && [ "${ALLOW_SMRI_BIN_IN_JOB:-0}" != "1" ]; then
    echo "Do not submit this bin entrypoint with sbatch. Run it on the login node with bash; it will submit only the heavy jobs internally." >&2
    exit 2
fi

if [ "$#" -lt 1 ]; then
    usage
    exit 2
fi

BATCH_DIR=$1
shift
QC_EXCEL=""
DRY_RUN=0
SUBMIT=0
RUN_MASKALL_LOCAL=0
STAGE1_ONLY=0
SUBMIT_DENOISE=1
RUN_DENOISING_ONLY=0
RUN_DENOISING_START=0
RUN_ACPC_START=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --qc-excel)
            QC_EXCEL=${2:?--qc-excel requires a path}
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --submit)
            SUBMIT=1
            shift
            ;;
        --stage1-only)
            STAGE1_ONLY=1
            shift
            ;;
        --no-denoise-submit)
            SUBMIT_DENOISE=0
            shift
            ;;
        --acpc-start|--acpcStart)
            RUN_ACPC_START=1
            shift
            ;;
        --denoising)
            RUN_DENOISING_ONLY=1
            shift
            ;;
        --denoising-start|--denoisingStart)
            RUN_DENOISING_START=1
            shift
            ;;
        --run-maskall-local)
            RUN_MASKALL_LOCAL=1
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
BATCH_DIR=$(cd "$BATCH_DIR" && pwd)
PYTHON_BIN=${PYTHON:-python}
MANIFEST_DIR="${BATCH_DIR}/manifests"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

mkdir -p \
    "${BATCH_DIR}/1_T2toT1/data" \
    "${BATCH_DIR}/1_T2toT1/qc" \
    "${BATCH_DIR}/1_T2toT1/logs" \
    "${BATCH_DIR}/2_nnunet_input/imagesTs" \
    "${BATCH_DIR}/2_nnunet_output/logs" \
    "${BATCH_DIR}/3_skullstrip/data" \
    "${BATCH_DIR}/3_skullstrip/logs" \
    "$MANIFEST_DIR" \
    "${BATCH_DIR}/logs"

echo "=== sMRI preprocessing V2 ==="
echo "BATCH_DIR=$BATCH_DIR"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "PYTHON=$PYTHON_BIN"

wait_for_slurm_jobs() {
    local label=$1
    shift
    local raw_jobs=("$@")
    local jobs=()
    local poll_seconds=${SMRI_POLL_SECONDS:-60}
    local active_count
    local failed=0
    local state
    local job

    if [ "${#raw_jobs[@]}" -eq 0 ]; then
        return 0
    fi

    for job in "${raw_jobs[@]}"; do
        job="${job%%;*}"
        if [ -n "$job" ]; then
            jobs+=("$job")
        fi
    done

    if [ "${#jobs[@]}" -eq 0 ]; then
        return 0
    fi

    echo "[wait] ${label}: ${jobs[*]}"
    while true; do
        active_count=$(squeue -h -j "$(IFS=,; echo "${jobs[*]}")" 2>/dev/null | wc -l)
        if [ "$active_count" -eq 0 ]; then
            break
        fi
        echo "[wait] ${label}: ${active_count} job(s) still in queue; sleeping ${poll_seconds}s"
        sleep "$poll_seconds"
    done

    if command -v sacct >/dev/null 2>&1; then
        for job in "${jobs[@]}"; do
            state=$(sacct -n -X -j "$job" --format=State 2>/dev/null | awk 'NF {print $1; exit}')
            echo "[wait] ${label}: job ${job} final state: ${state:-unknown}"
            case "${state:-unknown}" in
                COMPLETED|COMPLETING|unknown)
                    ;;
                *)
                    failed=1
                    ;;
            esac
        done
    else
        echo "[wait] sacct not found; job final states were not checked."
    fi
    return "$failed"
}

run_maskall_local() {
    echo "[local] check registration and nnU-Net outputs"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/4_check_t2tot1_outputs_v2.py" --batch-dir "$BATCH_DIR"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/5_check_nnunet_outputs_v2.py" --batch-dir "$BATCH_DIR"
    echo "[local] run mask_all serially"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/6_mask_all_v2.py" --batch-dir "$BATCH_DIR"
}

ensure_acpc_split() {
    if [ ! -d "${BATCH_DIR}/3_skullstrip/data" ]; then
        echo "Cannot start ACPC: 4_results has no subjects and 3_skullstrip/data is missing." >&2
        echo "Run the full preprocessing workflow with --submit, or rerun mask_all first if registration and nnU-Net outputs already exist." >&2
        exit 2
    fi

    echo "[local] check/repair 4_results split from 3_skullstrip/data"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/7_split_for_acpc_v2.py" --batch-dir "$BATCH_DIR"
}

registration_ready() {
    "$PYTHON_BIN" - "$BATCH_DIR" <<'PY'
import sys
from pathlib import Path

batch = Path(sys.argv[1])
data = batch / "1_T2toT1" / "data"
subjects = [p for p in data.iterdir() if p.is_dir()] if data.is_dir() else []
if not subjects:
    raise SystemExit(1)
for subject in subjects:
    if not (subject / "T1.nii.gz").is_file():
        raise SystemExit(1)
    t2 = subject / "T2.nii.gz"
    reg = subject / "registration" / "T2_to_T1.nii.gz"
    if t2.is_file() and t2.stat().st_size > 0 and not (reg.is_file() and reg.stat().st_size > 0):
        raise SystemExit(1)
raise SystemExit(0)
PY
}

nnunet_ready() {
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/5_check_nnunet_outputs_v2.py" --batch-dir "$BATCH_DIR" --require-all >/dev/null 2>&1
}

skullstrip_ready() {
    "$PYTHON_BIN" - "$BATCH_DIR" <<'PY'
import csv
import sys
from pathlib import Path

batch = Path(sys.argv[1])
map_path = batch / "2_nnunet_input" / "nnunet_id_map.csv"
if not map_path.is_file():
    raise SystemExit(1)
with map_path.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
if not rows:
    raise SystemExit(1)
for row in rows:
    subject = row.get("subject_name", "")
    if not subject:
        raise SystemExit(1)
    source = batch / "1_T2toT1" / "data" / subject
    out = batch / "3_skullstrip" / "data" / subject
    for name in ["T1.nii.gz", "mask.nii.gz"]:
        path = out / name
        if not (path.is_file() and path.stat().st_size > 0):
            raise SystemExit(1)
    reg = source / "registration" / "T2_to_T1.nii.gz"
    if reg.is_file() and reg.stat().st_size > 0:
        t2 = out / "T2.nii.gz"
        if not (t2.is_file() and t2.stat().st_size > 0):
            raise SystemExit(1)
raise SystemExit(0)
PY
}

count_selected_for_denoise() {
    local summary="${MANIFEST_DIR}/20_questionable_summary.csv"
    if [ ! -f "$summary" ]; then
        echo 0
        return 0
    fi
    awk -F, '
        NR == 1 {
            for (i = 1; i <= NF; i++) {
                if ($i == "status") status_col = i
            }
            next
        }
        status_col && $status_col == "selected_for_denoise" {count++}
        END {print count+0}
    ' "$summary"
}

count_existing_denoise_inputs() {
    local input_root="${BATCH_DIR}/5_questionable/input"
    local output_root="${BATCH_DIR}/5_questionable/output"
    local count=0
    if [ -d "$input_root" ]; then
        count=$((count + $(find "$input_root" -mindepth 2 -maxdepth 2 -type f -name T1.nii.gz | wc -l)))
    fi
    if [ -d "$output_root" ]; then
        count=$((count + $(find "$output_root" -mindepth 2 -maxdepth 2 -type f -name T1_age.nii.gz | wc -l)))
    fi
    echo "$count"
}

run_denoise_selection() {
    echo "[local] select Fail/Questionable subjects for denoise"
    QUESTION_ARGS=(--batch-dir "$BATCH_DIR" --pipeline-dir "$PIPELINE_DIR")
    if [ -n "$QC_EXCEL" ]; then
        QUESTION_ARGS+=(--qc-excel "$QC_EXCEL")
    fi
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/10_select_denoise_candidates_v2.py" "${QUESTION_ARGS[@]}" || true
}

submit_denoise_if_needed() {
    local mode=${1:-selected}
    local count=0
    DENOISE_JOB=""
    if [ "$mode" = "existing-input" ]; then
        count=$(count_existing_denoise_inputs)
    else
        count=$(count_selected_for_denoise)
    fi
    if [ "$count" -gt 0 ] && [ "$SUBMIT_DENOISE" -eq 1 ]; then
        DENOISE_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/denoise_moardiff.sh" "$BATCH_DIR" "$PIPELINE_DIR")
        echo "$DENOISE_JOB" > "${MANIFEST_DIR}/denoise_job_id.txt"
        echo "Submitted denoise job: $DENOISE_JOB"
    else
        echo "Denoise job not submitted. selected_or_input=${count}, submit_denoise=${SUBMIT_DENOISE}"
    fi
}

submit_acpc_and_qc() {
    T1T2_ACPC_JOB=""
    JUSTT1_ACPC_JOB=""
    T1T2_QC_JOB=""
    JUSTT1_QC_JOB=""
    ACPC_DEPENDENCIES=""

    for BRANCH in T1T2 justT1; do
        BRANCH_DIR="${BATCH_DIR}/4_results/${BRANCH}"
        if [ ! -d "$BRANCH_DIR" ]; then
            echo "No ${BRANCH} branch directory; skipping ACPC."
            continue
        fi
        COUNT=$(find "$BRANCH_DIR" -mindepth 1 -maxdepth 1 -type d ! -name qc | wc -l)
        if [ "$COUNT" -eq 0 ]; then
            echo "No subjects in ${BRANCH}; skipping ACPC."
            continue
        fi
        JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/acpc_preprocessing.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$BRANCH")
        QC_JOB=$(sbatch --parsable --dependency=afterany:${JOB} "${PIPELINE_DIR}/scripts/jobs/qc_acpc_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR" "$BRANCH")
        ACPC_DEPENDENCIES="${ACPC_DEPENDENCIES} ${QC_JOB}"
        if [ "$BRANCH" = "T1T2" ]; then
            T1T2_ACPC_JOB="$JOB"
            T1T2_QC_JOB="$QC_JOB"
        else
            JUSTT1_ACPC_JOB="$JOB"
            JUSTT1_QC_JOB="$QC_JOB"
        fi
        echo "Submitted ${BRANCH} ACPC job ${JOB}; QC job ${QC_JOB}"
    done

    if [ -n "${ACPC_DEPENDENCIES// /}" ]; then
        wait_for_slurm_jobs "ACPC QC" $ACPC_DEPENDENCIES || true
    fi

    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/8_check_acpc_outputs_v2.py" --batch-dir "$BATCH_DIR" || true
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/9_check_acpc_qc_outputs_v2.py" --batch-dir "$BATCH_DIR" || true
}

run_post_maskall_flow() {
    if [ "$STAGE1_ONLY" -eq 1 ]; then
        {
            echo "reg_job_id,nnunet_job_id,mask_all_job_id,t1t2_acpc_job_id,justt1_acpc_job_id,t1t2_qc_job_id,justt1_qc_job_id,denoise_job_id"
            echo "${REG_JOB},${NNUNET_JOB},${MASK_JOB},,,,,"
        } > "${MANIFEST_DIR}/submitted_jobs.csv"
        "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
        echo "Stage1-only mode complete after mask_all checkpoint."
        echo "Readable report: ${BATCH_DIR}/logs/preprocessing_report.md"
        exit 0
    fi

    ensure_acpc_split
    submit_acpc_and_qc

    echo "[local] select Fail/Questionable subjects for denoise"
    run_denoise_selection

    DENOISE_JOB=""
    submit_denoise_if_needed selected

    {
        echo "reg_job_id,nnunet_job_id,mask_all_job_id,t1t2_acpc_job_id,justt1_acpc_job_id,t1t2_qc_job_id,justt1_qc_job_id,denoise_job_id"
        echo "${REG_JOB},${NNUNET_JOB},${MASK_JOB},${T1T2_ACPC_JOB},${JUSTT1_ACPC_JOB},${T1T2_QC_JOB},${JUSTT1_QC_JOB},${DENOISE_JOB}"
    } > "${MANIFEST_DIR}/submitted_jobs.csv"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"

    echo "mask_all mode: $MASK_JOB"
    echo "Wrote ${MANIFEST_DIR}/submitted_jobs.csv"
    echo "Readable report: ${BATCH_DIR}/logs/preprocessing_report.md"
}

if [ $((RUN_ACPC_START + RUN_DENOISING_START + RUN_DENOISING_ONLY)) -gt 1 ]; then
    echo "Use only one resume option: --acpc-start, --denoising-start, or --denoising." >&2
    exit 2
fi

if [ "$RUN_MASKALL_LOCAL" -eq 1 ]; then
    run_maskall_local
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    exit 0
fi

if [ "$RUN_DENOISING_START" -eq 1 ]; then
    if ! command -v sbatch >/dev/null 2>&1 && [ "$SUBMIT_DENOISE" -eq 1 ]; then
        echo "sbatch not found. Run this entrypoint on the cluster login node with Slurm available." >&2
        exit 2
    fi
    run_denoise_selection
    submit_denoise_if_needed selected
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    echo "Readable report: ${BATCH_DIR}/logs/preprocessing_report.md"
    exit 0
fi

if [ "$RUN_ACPC_START" -eq 1 ]; then
    if ! command -v sbatch >/dev/null 2>&1; then
        echo "sbatch not found. Run this entrypoint on the cluster login node with Slurm available." >&2
        exit 2
    fi
    ensure_acpc_split
    submit_acpc_and_qc
    run_denoise_selection
    submit_denoise_if_needed selected
    {
        echo "reg_job_id,nnunet_job_id,mask_all_job_id,t1t2_acpc_job_id,justt1_acpc_job_id,t1t2_qc_job_id,justt1_qc_job_id,denoise_job_id"
        echo ",,,${T1T2_ACPC_JOB},${JUSTT1_ACPC_JOB},${T1T2_QC_JOB},${JUSTT1_QC_JOB},${DENOISE_JOB}"
    } > "${MANIFEST_DIR}/submitted_jobs.csv"
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    echo "Readable report: ${BATCH_DIR}/logs/preprocessing_report.md"
    exit 0
fi

if [ "$RUN_DENOISING_ONLY" -eq 1 ]; then
    if ! command -v sbatch >/dev/null 2>&1 && [ "$SUBMIT_DENOISE" -eq 1 ]; then
        echo "sbatch not found. Run this entrypoint on the cluster login node with Slurm available." >&2
        exit 2
    fi
    if [ "$(count_existing_denoise_inputs)" -eq 0 ]; then
        echo "[checkpoint] no existing denoise input/output found; rebuilding 5_questionable from 4_results and QC Excel."
        run_denoise_selection
    fi
    submit_denoise_if_needed existing-input
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    echo "Readable report: ${BATCH_DIR}/logs/preprocessing_report.md"
    exit 0
fi

echo "[local] standardize T1/T2 names"
if [ "$DRY_RUN" -eq 1 ]; then
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/1_standardize_t1_t2_v2.py" --batch-dir "$BATCH_DIR" --dry-run
else
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/1_standardize_t1_t2_v2.py" --batch-dir "$BATCH_DIR"
fi

echo "[local] add/check age suffix"
AGE_ARGS=(--batch-dir "$BATCH_DIR" --pipeline-dir "$PIPELINE_DIR")
if [ -n "$QC_EXCEL" ]; then
    AGE_ARGS+=(--qc-excel "$QC_EXCEL")
fi
if [ "$DRY_RUN" -eq 1 ]; then
    AGE_ARGS+=(--dry-run)
fi
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/2_add_age_suffix_v2.py" "${AGE_ARGS[@]}"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry run complete. It stops before nnU-Net input prep because rename/age changes were not materialized."
    exit 0
fi

echo "[local] prepare nnU-Net input, dataset.json, and id map"
NNUNET_PREP_ARGS=(--batch-dir "$BATCH_DIR")
"$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/3_prepare_nnunet_input_v2.py" "${NNUNET_PREP_ARGS[@]}"

if [ "$SUBMIT" -eq 0 ]; then
    "$PYTHON_BIN" "${PIPELINE_DIR}/scripts/steps/11_write_preprocessing_report_v2.py" --batch-dir "$BATCH_DIR"
    echo "Local preparation complete. Use --submit to submit the Slurm preprocessing workflow."
    exit 0
fi

if ! command -v sbatch >/dev/null 2>&1; then
    echo "sbatch not found. Run this entrypoint on the cluster login node with Slurm available." >&2
    exit 2
fi

REG_JOB=""
NNUNET_JOB=""
MASK_JOB=""

if skullstrip_ready; then
    echo "[checkpoint] 3_skullstrip outputs already complete; skipping registration, nnU-Net, and mask_all."
    REG_JOB="skipped_existing_skullstrip"
    NNUNET_JOB="skipped_existing_skullstrip"
    MASK_JOB="skipped_existing_skullstrip"
elif registration_ready && nnunet_ready; then
    echo "[checkpoint] registration and nnU-Net outputs already complete; submitting mask_all only."
    REG_JOB="skipped_existing_registration"
    NNUNET_JOB="skipped_existing_nnunet"
    ##############################
    # mask_all mode: login-node/local fallback. Disabled by default; uncomment the next two lines and comment out the Slurm block below to use it.
    # MASK_JOB="local"
    # run_maskall_local
    ##############################
    ##############################
    # Choose exactly one mask_all location: local/login-node block above or Slurm job block below. Default is Slurm job.
    ##############################
    ##############################
    # mask_all mode: Slurm job default. No dependency is needed because registration and nnU-Net are already complete.
    MASK_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/mask_all.sh" "$BATCH_DIR" "$PIPELINE_DIR")
    echo "Submitted mask_all job: $MASK_JOB"
    wait_for_slurm_jobs "mask_all" "$MASK_JOB" || true
    ##############################
else
    REG_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/sMRI_pipeline_step0_reg2_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR")
    NNUNET_JOB=$(sbatch --parsable "${PIPELINE_DIR}/scripts/jobs/nnunet_task523.sh" "$BATCH_DIR" "$PIPELINE_DIR")
    echo "Submitted registration job: $REG_JOB"
    echo "Submitted nnU-Net job: $NNUNET_JOB"

    ##############################
    # mask_all mode: login-node/local fallback. Disabled by default; uncomment every line in this block and comment out the Slurm block below to use it.
    # wait_for_slurm_jobs "registration and nnU-Net" "$REG_JOB" "$NNUNET_JOB" || true
    # MASK_JOB="local"
    # run_maskall_local
    ##############################
    ##############################
    # Choose exactly one mask_all location: local/login-node block above or Slurm job block below. Default is Slurm job.
    ##############################
    ##############################
    # mask_all mode: Slurm job default. Slurm dependency waits for reg + nnU-Net; console waits for mask_all before local split.
    MASK_JOB=$(sbatch --parsable --dependency=afterany:${REG_JOB}:${NNUNET_JOB} "${PIPELINE_DIR}/scripts/jobs/mask_all.sh" "$BATCH_DIR" "$PIPELINE_DIR")
    echo "Submitted mask_all job: $MASK_JOB"
    echo "mask_all dependency: afterany:${REG_JOB}:${NNUNET_JOB}"
    echo "Waiting for mask_all means waiting for registration + nnU-Net + mask_all to finish."
    wait_for_slurm_jobs "mask_all" "$MASK_JOB" || true
    ##############################
fi

run_post_maskall_flow
