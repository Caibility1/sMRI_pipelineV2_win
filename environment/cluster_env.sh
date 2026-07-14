#!/bin/bash
# Source this file on the cluster login node before running the sMRI pipeline.
#
# Usage:
#   source /public_bme2/bme-zhanghan/linmo2025/sMRI_pipelineV2/environment/cluster_env.sh
#   bash "$PIPELINE_DIR/bin/smri_preprocessing.sh" <BATCH_DIR> --submit
#
# Keep .bashrc limited to generic conda initialization. Pipeline/model paths live
# here so they can later be moved into Singularity/Apptainer bind arguments.

# ---- Pipeline root ---------------------------------------------------------
export PIPELINE_DIR="${PIPELINE_DIR:-/public_bme2/bme-zhanghan/linmo2025/sMRI_pipelineV2}"
export SMRI_DATA_ROOT="${SMRI_DATA_ROOT:-/public_bme2/bme-zhanghan/linmo2025}"
export SMRI_QC_DIR="${SMRI_QC_DIR:-$PIPELINE_DIR}"

# ---- Conda activation used inside Slurm jobs -------------------------------
# If your conda is not in one of these common locations, override before sourcing:
#   export SMRI_CONDA_SH=/path/to/miniforge/etc/profile.d/conda.sh
if [ -n "${SMRI_CONDA_SH:-}" ] && [ ! -f "$SMRI_CONDA_SH" ]; then
    echo "WARN: ignoring missing SMRI_CONDA_SH=$SMRI_CONDA_SH" >&2
    unset SMRI_CONDA_SH
fi
if [ -z "${SMRI_CONDA_SH:-}" ]; then
    for candidate in \
        "$HOME/miniforge3/etc/profile.d/conda.sh" \
        "$HOME/miniconda3/etc/profile.d/conda.sh" \
        "$HOME/anaconda3/etc/profile.d/conda.sh" \
        "/home_data/home/${USER}/miniforge3/etc/profile.d/conda.sh" \
        "/home_data/home/${USER}/miniconda3/etc/profile.d/conda.sh"; do
        if [ -f "$candidate" ]; then
            export SMRI_CONDA_SH="$candidate"
            break
        fi
    done
fi
export SMRI_CONDA_SH="${SMRI_CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"
export SMRI_PIPELINE_CONDA_ENV="${SMRI_PIPELINE_CONDA_ENV:-sMRI_pipeline}"

# nnU-Net and moAR-Diff jobs read these explicit variables and activate the env
# inside sbatch, so they do not depend on the interactive shell state.
export SMRI_NNUNET_CONDA_SH="${SMRI_NNUNET_CONDA_SH:-$SMRI_CONDA_SH}"
export SMRI_NNUNET_CONDA_ENV="${SMRI_NNUNET_CONDA_ENV:-$SMRI_PIPELINE_CONDA_ENV}"
export SMRI_DENOISE_CONDA_SH="${SMRI_DENOISE_CONDA_SH:-$SMRI_CONDA_SH}"
export SMRI_DENOISE_CONDA_ENV="${SMRI_DENOISE_CONDA_ENV:-$SMRI_PIPELINE_CONDA_ENV}"

# Optional: activate locally too, useful for the lightweight Python steps that
# run directly from the console.
if [ -f "$SMRI_CONDA_SH" ]; then
    # shellcheck disable=SC1090
    source "$SMRI_CONDA_SH"
    conda activate "$SMRI_PIPELINE_CONDA_ENV"
else
    echo "WARN: conda activation script not found: $SMRI_CONDA_SH" >&2
fi

# ---- nnU-Net v1 Task523 resources -----------------------------------------
# Prefer the pipeline-local copy when it exists. This intentionally overrides
# stale exported nnU-Net variables from older shells; use SMRI_NNUNET_RESOURCE_DIR
# when you really want to point at another resource tree.
if [ -n "${SMRI_NNUNET_RESOURCE_DIR:-}" ]; then
    export NNUNET_RESOURCE_DIR="$SMRI_NNUNET_RESOURCE_DIR"
elif [ -d "$PIPELINE_DIR/resources/models/nnUNet" ]; then
    export NNUNET_RESOURCE_DIR="$PIPELINE_DIR/resources/models/nnUNet"
else
    export NNUNET_RESOURCE_DIR="/public_bme2/bme-zhanghan/linmo2025/resources/models/nnUNet"
fi
export NNUNET_DATA_DIR="$NNUNET_RESOURCE_DIR/nnUNetData"
export nnUNet_raw_data_base="$NNUNET_DATA_DIR/nnUNet_raw_data_base"
export nnUNet_preprocessed="$NNUNET_DATA_DIR/nnUNet_preprocessed"
export RESULTS_FOLDER="$NNUNET_DATA_DIR/RESULTS_FOLDER"

# nnU-Net inference policy. Defaults intentionally match the original command:
# nnUNet_predict -i <input> -o <output> -m 3d_fullres -t 523
# That means all available folds are used automatically and TTA is enabled.
# Use SMRI_NNUNET_CUDA_CHECK_ONLY=1 or the job flag --cuda-check-only only for
# quick environment checks.
unset NNUNET_FOLDS
unset NNUNET_DISABLE_TTA
unset NNUNET_REQUIRE_CUDA
export SMRI_NNUNET_TASK_NAME="${SMRI_NNUNET_TASK_NAME:-523}"
export SMRI_NNUNET_FOLDS="${SMRI_NNUNET_FOLDS:-}"
export SMRI_NNUNET_DISABLE_TTA="${SMRI_NNUNET_DISABLE_TTA:-0}"
export SMRI_NNUNET_REQUIRE_CUDA="${SMRI_NNUNET_REQUIRE_CUDA:-1}"
export SMRI_NNUNET_CUDA_CHECK_ONLY="${SMRI_NNUNET_CUDA_CHECK_ONLY:-0}"

# ---- moAR-Diff denoise resources ------------------------------------------
# Prefer a valid pipeline-local model. A stale MOARDIFF_DIR from an older shell
# is ignored unless it actually contains main.py.
if [ -n "${SMRI_MOARDIFF_DIR:-}" ]; then
    export MOARDIFF_DIR="$SMRI_MOARDIFF_DIR"
elif [ -n "${MOARDIFF_DIR:-}" ] && [ -f "$MOARDIFF_DIR/main.py" ]; then
    export MOARDIFF_DIR="$MOARDIFF_DIR"
elif [ -f "$PIPELINE_DIR/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune/main.py" ]; then
    export MOARDIFF_DIR="$PIPELINE_DIR/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune"
elif [ -f "$PIPELINE_DIR/resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune/main.py" ]; then
    export MOARDIFF_DIR="$PIPELINE_DIR/resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune"
else
    export MOARDIFF_DIR="/public_bme2/bme-zhanghan/linmo2025/resources/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune"
fi
if [ -z "${MOARDIFF_CKPT:-}" ] || [ ! -f "${MOARDIFF_CKPT:-}" ]; then
    export MOARDIFF_CKPT="$MOARDIFF_DIR/exp/logs/finetuneDPM_with_age/ckpt_100000.pth"
fi
export MOARDIFF_CONFIG_NAME="${MOARDIFF_CONFIG_NAME:-inference.yml}"

# If you later run denoise through Singularity/Apptainer, uncomment and set:
# export SMRI_DENOISE_CONTAINER=/path/to/smri_denoise.sif
# export SMRI_CONTAINER_ENGINE=apptainer
# export SMRI_DENOISE_BIND_ARGS="-B /public_bme2:/public_bme2"

# ---- Resource paths used by ACPC/recon wrappers ----------------------------
# Keep these here for now. During containerization, revisit FreeSurfer infant:
# ACPC appears to source it historically but does not currently call FS tools.
if [ -z "${SMRI_TEMPLATE_DIR:-}" ]; then
    if [ -d "$PIPELINE_DIR/resources/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0" ]; then
        export SMRI_TEMPLATE_DIR="$PIPELINE_DIR/resources/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0"
    else
        export SMRI_TEMPLATE_DIR="/public_bme/data/zhanghan_group/sMRI_pipeline_new/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0"
    fi
fi
if [ -z "${SMRI_WORKBENCH_BIN:-}" ]; then
    if [ -d "$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64" ]; then
        export SMRI_WORKBENCH_BIN="$PIPELINE_DIR/resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
    else
        export SMRI_WORKBENCH_BIN="/public_bme/home/zhanghan_group_public/software/workbench-linux64-v2.0.0/workbench/bin_linux64"
    fi
fi

# ---- Orchestrator behavior -------------------------------------------------
export SMRI_POLL_SECONDS="${SMRI_POLL_SECONDS:-60}"

echo "sMRI pipeline cluster env loaded"
echo "PIPELINE_DIR=$PIPELINE_DIR"
echo "SMRI_DATA_ROOT=$SMRI_DATA_ROOT"
echo "SMRI_QC_DIR=$SMRI_QC_DIR"
echo "SMRI_PIPELINE_CONDA_ENV=$SMRI_PIPELINE_CONDA_ENV"
echo "NNUNET_RESOURCE_DIR=$NNUNET_RESOURCE_DIR"
echo "SMRI_NNUNET_FOLDS=${SMRI_NNUNET_FOLDS:-auto/all folds}"
echo "SMRI_NNUNET_DISABLE_TTA=$SMRI_NNUNET_DISABLE_TTA"
echo "MOARDIFF_DIR=$MOARDIFF_DIR"
