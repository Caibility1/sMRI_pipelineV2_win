#!/usr/bin/env bash
# Read-only WSL2 deployment checker for sMRI Pipeline V2.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PIPELINE_DIR

if [ -f "$SCRIPT_DIR/wsl_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/wsl_env.sh" >/dev/null
fi

ok=0
missing=0

print_header() {
    printf '\n== %s ==\n' "$1"
}

check_cmd() {
    label="$1"
    cmd="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        printf '[OK]      %-28s %s\n' "$label" "$(command -v "$cmd")"
        ok=$((ok + 1))
    else
        printf '[MISSING] %-28s command not found: %s\n' "$label" "$cmd"
        missing=$((missing + 1))
    fi
}

check_path() {
    label="$1"
    path="$2"
    if [ -e "$path" ]; then
        printf '[OK]      %-28s %s\n' "$label" "$path"
        ok=$((ok + 1))
    else
        printf '[MISSING] %-28s %s\n' "$label" "$path"
        missing=$((missing + 1))
    fi
}

check_python_import() {
    label="$1"
    module="$2"
    python_bin="${3:-python3}"
    if command -v "$python_bin" >/dev/null 2>&1 && "$python_bin" -c "import ${module}" >/dev/null 2>&1; then
        printf '[OK]      %-28s %s imports %s\n' "$label" "$python_bin" "$module"
        ok=$((ok + 1))
    else
        printf '[MISSING] %-28s %s cannot import %s\n' "$label" "$python_bin" "$module"
        missing=$((missing + 1))
    fi
}

print_header "System"
printf 'Distro:   %s\n' "$(grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
printf 'Kernel:   %s\n' "$(uname -r)"
printf 'Pipeline: %s\n' "$PIPELINE_DIR"
printf 'User:     %s\n' "$(id -un)"

print_header "FSL"
printf 'FSLDIR:   %s\n' "${FSLDIR:-<not set>}"
check_cmd "flirt" flirt
check_cmd "fslmaths" fslmaths
check_cmd "slicer" slicer
check_cmd "pngappend" pngappend
if command -v flirt >/dev/null 2>&1; then
    flirt -version 2>/dev/null | head -1 || true
fi

print_header "ANTs"
printf 'ANTSPATH: %s\n' "${ANTSPATH:-<not set>}"
check_cmd "N4BiasFieldCorrection" N4BiasFieldCorrection
check_cmd "antsRegistration" antsRegistration

print_header "Connectome Workbench"
printf 'SMRI_WORKBENCH_BIN: %s\n' "${SMRI_WORKBENCH_BIN:-<not set>}"
check_cmd "wb_command" wb_command
if command -v wb_command >/dev/null 2>&1; then
    wb_command -version 2>/dev/null | head -2 || true
fi

print_header "FreeSurfer"
printf 'FREESURFER_HOME: %s\n' "${FREESURFER_HOME:-<not set>}"
printf 'FS_LICENSE:      %s\n' "${FS_LICENSE:-<not set>}"
check_cmd "infant_recon_all" infant_recon_all
check_cmd "recon-all" recon-all
check_cmd "freeview" freeview
if [ -n "${FS_LICENSE:-}" ]; then
    check_path "FreeSurfer license" "$FS_LICENSE"
else
    printf '[MISSING] %-28s FS_LICENSE is not set\n' "FreeSurfer license"
    missing=$((missing + 1))
fi

print_header "nnU-Net v1"
printf 'nnUNet_raw_data_base: %s\n' "${nnUNet_raw_data_base:-<not set>}"
printf 'nnUNet_preprocessed:  %s\n' "${nnUNet_preprocessed:-<not set>}"
printf 'RESULTS_FOLDER:       %s\n' "${RESULTS_FOLDER:-<not set>}"
printf 'SMRI_NNUNET_CONDA_SH:  %s\n' "${SMRI_NNUNET_CONDA_SH:-<not set>}"
printf 'SMRI_NNUNET_MAMBA_EXE: %s\n' "${SMRI_NNUNET_MAMBA_EXE:-<not set>}"
printf 'SMRI_NNUNET_CONDA_ENV: %s\n' "${SMRI_NNUNET_CONDA_ENV:-<not set>}"
check_path "Task523 model" "${RESULTS_FOLDER:-}/nnUNet/3d_fullres/Task523_CBCPSkullStrip"
check_path "nnU-Net source" "${NNUNET_RESOURCE_DIR:-}/nnunet"
check_cmd "nnUNet_predict" nnUNet_predict
check_python_import "python torch" torch python3

print_header "moAR-Diff"
printf 'MOARDIFF_DIR:  %s\n' "${MOARDIFF_DIR:-<not set>}"
printf 'MOARDIFF_CKPT: %s\n' "${MOARDIFF_CKPT:-<not set>}"
printf 'SMRI_DENOISE_CONDA_SH:  %s\n' "${SMRI_DENOISE_CONDA_SH:-<not set>}"
printf 'SMRI_DENOISE_MAMBA_EXE: %s\n' "${SMRI_DENOISE_MAMBA_EXE:-<not set>}"
printf 'SMRI_DENOISE_CONDA_ENV: %s\n' "${SMRI_DENOISE_CONDA_ENV:-<not set>}"
check_path "moAR-Diff directory" "${MOARDIFF_DIR:-}"
check_path "moAR-Diff checkpoint" "${MOARDIFF_CKPT:-}"

print_header "Python/GPU"
check_cmd "python3" python3
if command -v conda >/dev/null 2>&1; then
    printf '[OK]      %-28s %s\n' "conda/micromamba" "$(command -v conda)"
    ok=$((ok + 1))
elif command -v micromamba >/dev/null 2>&1; then
    printf '[OK]      %-28s %s\n' "conda/micromamba" "$(command -v micromamba)"
    ok=$((ok + 1))
else
    printf '[MISSING] %-28s command not found: conda or micromamba\n' "conda/micromamba"
    missing=$((missing + 1))
fi
check_cmd "nvidia-smi" nvidia-smi
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | head -1 || true
fi

print_header "Summary"
printf 'OK: %s\n' "$ok"
printf 'Missing: %s\n' "$missing"
if [ "$missing" -gt 0 ]; then
    exit 1
fi
