#!/usr/bin/env bash
set -euo pipefail

PIPELINE_DIR="${PIPELINE_DIR:-/opt/smri/pipeline}"
PYTHON="${PYTHON:-/opt/micromamba/envs/sMRI_pipeline_win/bin/python}"
export PIPELINE_DIR PYTHON

show_help() {
    cat <<'EOF'
sMRI Pipeline Windows container runtime

Commands:
  preprocess  BATCH_DIR [pipeline options]
  postprocess BATCH_DIR [pipeline options]
  doctor
  shell

Examples inside the container:
  preprocess /data --submit --age-source folder --qc-mode all-pass
  postprocess /data --submit --recon-jobs 2
EOF
}

doctor() {
    local failed=0
    for program in "$PYTHON" bash flirt N4BiasFieldCorrection wb_command infant_recon_all; do
        if command -v "$program" >/dev/null 2>&1 || [[ -x "$program" ]]; then
            printf '[OK] %s\n' "$program"
        else
            printf '[MISSING] %s\n' "$program" >&2
            failed=1
        fi
    done
    for path in "$NNUNET_RESOURCE_DIR" "$MOARDIFF_CKPT" "$SMRI_TEMPLATE_DIR" "$PIPELINE_DIR/scripts/jobs/smri_container_runtime.py"; do
        if [[ -e "$path" ]]; then
            printf '[OK] %s\n' "$path"
        else
            printf '[MISSING] %s\n' "$path" >&2
            failed=1
        fi
    done
    if [[ -n "${FS_LICENSE:-}" && -f "$FS_LICENSE" ]]; then
        printf '[OK] FS_LICENSE=%s\n' "$FS_LICENSE"
    else
        printf '[WARN] FreeSurfer license is not mounted; preprocessing can start, recon cannot.\n'
    fi
    "$PYTHON" -c 'import nibabel, numpy, openpyxl, pandas, SimpleITK, torch; print("[OK] Python scientific stack; torch=" + torch.__version__)'
    return "$failed"
}

case "${1:-help}" in
    preprocess)
        shift
        exec "$PYTHON" "$PIPELINE_DIR/scripts/jobs/smri_container_runtime.py" preprocess "$@"
        ;;
    postprocess)
        shift
        exec "$PYTHON" "$PIPELINE_DIR/scripts/jobs/smri_container_runtime.py" postprocess "$@"
        ;;
    doctor)
        shift
        doctor "$@"
        ;;
    shell)
        shift
        exec bash "$@"
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        printf 'Unknown command: %s\n\n' "$1" >&2
        show_help >&2
        exit 2
        ;;
esac
