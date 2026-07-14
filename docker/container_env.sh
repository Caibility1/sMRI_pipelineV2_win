#!/usr/bin/env bash
# Runtime environment sourced by docker backend generated scripts.

export PIPELINE_DIR="${PIPELINE_DIR:-/pipeline}"
export BATCH_DIR="${BATCH_DIR:-/batch}"
export FSLOUTPUTTYPE="${FSLOUTPUTTYPE:-NIFTI_GZ}"

if [ -z "${FSLDIR:-}" ]; then
    for candidate in /opt/fsl /usr/local/fsl /fsl; do
        if [ -d "$candidate" ]; then
            export FSLDIR="$candidate"
            break
        fi
    done
fi
if [ -n "${FSLDIR:-}" ]; then
    export PATH="$FSLDIR/share/fsl/bin:$FSLDIR/bin:$PATH"
    if [ -f "$FSLDIR/etc/fslconf/fsl.sh" ]; then
        set +u
        # shellcheck disable=SC1090
        source "$FSLDIR/etc/fslconf/fsl.sh" || true
        set -u
    fi
fi

if [ -z "${ANTSPATH:-}" ]; then
    for candidate in /opt/ants/bin /usr/local/ants/bin /usr/lib/ants/bin; do
        if [ -x "$candidate/N4BiasFieldCorrection" ]; then
            export ANTSPATH="$candidate"
            break
        fi
    done
fi
if [ -n "${ANTSPATH:-}" ]; then
    export PATH="$ANTSPATH:$PATH"
fi

if [ -z "${SMRI_WORKBENCH_BIN:-}" ]; then
    if [ -d "$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64" ]; then
        export SMRI_WORKBENCH_BIN="$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
    elif [ -d /opt/workbench/bin_linux64 ]; then
        export SMRI_WORKBENCH_BIN=/opt/workbench/bin_linux64
    fi
fi
if [ -n "${SMRI_WORKBENCH_BIN:-}" ]; then
    export PATH="$PATH:$SMRI_WORKBENCH_BIN"
fi

if [ -z "${FREESURFER_HOME:-}" ]; then
    for candidate in "$PIPELINE_DIR/resources/software/freesurfer" /opt/freesurfer /usr/local/freesurfer /usr/local/freesurfer/8.1.0; do
        if [ -f "$candidate/SetUpFreeSurfer.sh" ]; then
            export FREESURFER_HOME="$candidate"
            break
        fi
    done
fi
if [ -z "${FS_LICENSE:-}" ] && [ -f /licenses/freesurfer/license.txt ]; then
    export FS_LICENSE=/licenses/freesurfer/license.txt
fi
if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then
    set +u
    # shellcheck disable=SC1090
    source "$FREESURFER_HOME/SetUpFreeSurfer.sh" >/dev/null 2>&1 || true
    set -u
fi

export NNUNET_RESOURCE_DIR="${NNUNET_RESOURCE_DIR:-$PIPELINE_DIR/resources/models/nnUNet}"
export NNUNET_DATA_DIR="${NNUNET_DATA_DIR:-$NNUNET_RESOURCE_DIR/nnUNetData}"
export nnUNet_raw_data_base="${nnUNet_raw_data_base:-$NNUNET_DATA_DIR/nnUNet_raw_data_base}"
export nnUNet_preprocessed="${nnUNet_preprocessed:-$NNUNET_DATA_DIR/nnUNet_preprocessed}"
export RESULTS_FOLDER="${RESULTS_FOLDER:-$NNUNET_DATA_DIR/RESULTS_FOLDER}"
if [ -d "$NNUNET_RESOURCE_DIR/nnunet" ]; then
    export PYTHONPATH="$NNUNET_RESOURCE_DIR:${PYTHONPATH:-}"
fi

export MOARDIFF_DIR="${MOARDIFF_DIR:-$PIPELINE_DIR/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune}"
export MOARDIFF_CKPT="${MOARDIFF_CKPT:-$MOARDIFF_DIR/exp/logs/finetuneDPM_with_age/ckpt_100000.pth}"
export MOARDIFF_CONFIG_NAME="${MOARDIFF_CONFIG_NAME:-inference.yml}"

ensure_smri_conda_first() {
    if [ -d /opt/micromamba/envs/sMRI_pipeline_win/bin ]; then
        export PATH="/opt/micromamba/envs/sMRI_pipeline_win/bin:/opt/micromamba/bin:$PATH"
    fi
}

ensure_smri_conda_first

