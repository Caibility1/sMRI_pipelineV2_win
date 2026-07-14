#!/usr/bin/env bash
# sMRI Pipeline V2 WSL2 environment.
# Source this file inside Ubuntu before running Linux-only jobs.

if [ -z "${PIPELINE_DIR:-}" ]; then
    WSL_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PIPELINE_DIR="$(cd "$WSL_ENV_DIR/.." && pwd)"
fi
export PIPELINE_DIR

# FSL: prefer the existing WSL install, then common install locations.
if [ -z "${FSLDIR:-}" ]; then
    for candidate in \
        "$HOME/fsl" \
        "/usr/local/fsl" \
        "/opt/fsl"; do
        if [ -d "$candidate" ]; then
            export FSLDIR="$candidate"
            break
        fi
    done
fi
if [ -n "${FSLDIR:-}" ]; then
    export PATH="$FSLDIR/share/fsl/bin:$FSLDIR/bin:$PATH"
    export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"
    if [ -f "$FSLDIR/etc/fslconf/fsl.sh" ]; then
        # shellcheck disable=SC1090
        source "$FSLDIR/etc/fslconf/fsl.sh"
    fi
fi

# ANTs: not bundled in this repository. Add a local install if present.
if [ -z "${ANTSPATH:-}" ]; then
    for candidate in \
        "$HOME/ants/bin" \
        "$HOME/ANTs/bin" \
        "/usr/local/ants/bin" \
        "/opt/ants/bin" \
        "/usr/lib/ants/bin"; do
        if [ -x "$candidate/N4BiasFieldCorrection" ]; then
            export ANTSPATH="$candidate"
            break
        fi
    done
fi
if [ -n "${ANTSPATH:-}" ]; then
    export PATH="$ANTSPATH:$PATH"
fi

# Connectome Workbench: use the copy bundled in resources.
if [ -z "${SMRI_WORKBENCH_BIN:-}" ]; then
    if [ -d "$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64" ]; then
        export SMRI_WORKBENCH_BIN="$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
    fi
fi
if [ -n "${SMRI_WORKBENCH_BIN:-}" ]; then
    export PATH="$PATH:$SMRI_WORKBENCH_BIN"
fi

# Conda/Mamba activation hooks used by nnU-Net and moAR-Diff job wrappers.
if [ -z "${SMRI_WSL_CONDA_SH:-}" ]; then
    for candidate in \
        "$HOME/miniforge3/etc/profile.d/conda.sh" \
        "$HOME/miniconda3/etc/profile.d/conda.sh" \
        "$HOME/mambaforge/etc/profile.d/conda.sh" \
        "$HOME/anaconda3/etc/profile.d/conda.sh" \
        "/opt/conda/etc/profile.d/conda.sh"; do
        if [ -f "$candidate" ]; then
            export SMRI_WSL_CONDA_SH="$candidate"
            break
        fi
    done
fi
if [ -z "${SMRI_WSL_MAMBA_EXE:-}" ]; then
    for candidate in \
        "$HOME/.local/bin/micromamba" \
        "$HOME/micromamba/bin/micromamba" \
        "/usr/local/bin/micromamba" \
        "/opt/conda/bin/micromamba"; do
        if [ -x "$candidate" ]; then
            export SMRI_WSL_MAMBA_EXE="$candidate"
            break
        fi
    done
fi
export SMRI_WSL_CONDA_ENV="${SMRI_WSL_CONDA_ENV:-sMRI_pipeline_win}"
if [ -n "${SMRI_WSL_CONDA_SH:-}" ]; then
    export SMRI_NNUNET_CONDA_SH="${SMRI_NNUNET_CONDA_SH:-$SMRI_WSL_CONDA_SH}"
    export SMRI_DENOISE_CONDA_SH="${SMRI_DENOISE_CONDA_SH:-$SMRI_WSL_CONDA_SH}"
fi
if [ -n "${SMRI_WSL_MAMBA_EXE:-}" ]; then
    export SMRI_NNUNET_MAMBA_EXE="${SMRI_NNUNET_MAMBA_EXE:-$SMRI_WSL_MAMBA_EXE}"
    export SMRI_DENOISE_MAMBA_EXE="${SMRI_DENOISE_MAMBA_EXE:-$SMRI_WSL_MAMBA_EXE}"
fi
export SMRI_NNUNET_CONDA_ENV="${SMRI_NNUNET_CONDA_ENV:-$SMRI_WSL_CONDA_ENV}"
export SMRI_DENOISE_CONDA_ENV="${SMRI_DENOISE_CONDA_ENV:-$SMRI_WSL_CONDA_ENV}"
for candidate in \
    "$HOME/.local/share/mamba/envs/$SMRI_WSL_CONDA_ENV/bin" \
    "$HOME/micromamba/envs/$SMRI_WSL_CONDA_ENV/bin" \
    "$HOME/miniforge3/envs/$SMRI_WSL_CONDA_ENV/bin" \
    "$HOME/miniconda3/envs/$SMRI_WSL_CONDA_ENV/bin" \
    "/opt/conda/envs/$SMRI_WSL_CONDA_ENV/bin"; do
    if [ -d "$candidate" ]; then
        export PATH="$candidate:$PATH"
        break
    fi
done
if [ -d "$HOME/.local/bin" ]; then
    export PATH="$HOME/.local/bin:$PATH"
fi
# FreeSurfer: prefer WSL-installed FreeSurfer 8.1, then the resource directory.
if [ -z "${FREESURFER_HOME:-}" ]; then
    for candidate in \
        "/usr/local/freesurfer/8.1.0" \
        "/usr/local/freesurfer" \
        "$PIPELINE_DIR/resources/software/freesurfer"; do
        if [ -f "$candidate/SetUpFreeSurfer.sh" ]; then
            export FREESURFER_HOME="$candidate"
            break
        fi
    done
fi
if [ -z "${FS_LICENSE:-}" ] && [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/license.txt" ]; then
    export FS_LICENSE="$FREESURFER_HOME/license.txt"
fi
if [ -z "${FS_LICENSE:-}" ] && [ -f "/usr/local/freesurfer/license.txt" ]; then
    export FS_LICENSE="/usr/local/freesurfer/license.txt"
fi
if [ -z "${FS_LICENSE:-}" ] && [ -f "$PIPELINE_DIR/resources/software/freesurfer/license.txt" ]; then
    export FS_LICENSE="$PIPELINE_DIR/resources/software/freesurfer/license.txt"
fi
if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then
    # shellcheck disable=SC1090
    source "$FREESURFER_HOME/SetUpFreeSurfer.sh" >/dev/null 2>&1 || true
fi

# nnU-Net v1 resources.
export NNUNET_RESOURCE_DIR="${NNUNET_RESOURCE_DIR:-$PIPELINE_DIR/resources/models/nnUNet}"
export NNUNET_DATA_DIR="${NNUNET_DATA_DIR:-$NNUNET_RESOURCE_DIR/nnUNetData}"
export nnUNet_raw_data_base="${nnUNet_raw_data_base:-$NNUNET_DATA_DIR/nnUNet_raw_data_base}"
export nnUNet_preprocessed="${nnUNet_preprocessed:-$NNUNET_DATA_DIR/nnUNet_preprocessed}"
export RESULTS_FOLDER="${RESULTS_FOLDER:-$NNUNET_DATA_DIR/RESULTS_FOLDER}"
if [ -d "$NNUNET_RESOURCE_DIR/nnunet" ]; then
    export PYTHONPATH="$NNUNET_RESOURCE_DIR:${PYTHONPATH:-}"
fi

# moAR-Diff resources.
export MOARDIFF_DIR="${MOARDIFF_DIR:-$PIPELINE_DIR/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune}"
export MOARDIFF_CKPT="${MOARDIFF_CKPT:-$MOARDIFF_DIR/exp/logs/finetuneDPM_with_age/ckpt_100000.pth}"
export MOARDIFF_CONFIG_NAME="${MOARDIFF_CONFIG_NAME:-inference.yml}"

missing=()
command -v flirt >/dev/null 2>&1 || missing+=("FSL/flirt")
command -v N4BiasFieldCorrection >/dev/null 2>&1 || missing+=("ANTs/N4BiasFieldCorrection")
command -v wb_command >/dev/null 2>&1 || missing+=("Workbench/wb_command")
command -v infant_recon_all >/dev/null 2>&1 || missing+=("FreeSurfer/infant_recon_all")
if [ "${#missing[@]}" -gt 0 ]; then
    echo "WARN: missing WSL tools: ${missing[*]}" >&2
fi


