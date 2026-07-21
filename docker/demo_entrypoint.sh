#!/usr/bin/env bash
set -euo pipefail

export PIPELINE_DIR=${PIPELINE_DIR:-/opt/smri/pipeline_demo}
if [ -f "${PIPELINE_DIR}/docker/container_env.sh" ]; then
    # shellcheck disable=SC1091
    source "${PIPELINE_DIR}/docker/container_env.sh"
fi

usage() {
    cat <<'EOF'
sMRI teaching container

Commands:
  reconstruct /data [options]  DICOM conversion and standard FreeSurfer recon-all
  stl /data [options]          Export reconstructed pial surfaces to STL
  doctor                       Check required programs and FreeSurfer license
  shell                        Open a Bash shell
EOF
}

command_name=${1:-help}
if [ "$#" -gt 0 ]; then shift; fi
case "$command_name" in
    reconstruct)
        exec bash "${PIPELINE_DIR}/scripts/jobs/smri_reconstruction_demo.sh" "$@"
        ;;
    stl)
        exec bash "${PIPELINE_DIR}/scripts/jobs/export_stl_demo.sh" "$@"
        ;;
    doctor)
        failed=0
        for tool in python3 dcm2niix flirt recon-all mris_convert; do
            if path=$(command -v "$tool" 2>/dev/null); then
                echo "[OK] $tool=$path"
            else
                echo "[FAIL] $tool not found" >&2
                failed=1
            fi
        done
        if [ -n "${FS_LICENSE:-}" ] && [ -s "$FS_LICENSE" ]; then
            echo "[OK] FS_LICENSE=$FS_LICENSE"
        else
            echo "[FAIL] mount a FreeSurfer license and set FS_LICENSE" >&2
            failed=1
        fi
        exit "$failed"
        ;;
    shell)
        exec /bin/bash "$@"
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "Unknown command: $command_name" >&2
        usage >&2
        exit 2
        ;;
esac
