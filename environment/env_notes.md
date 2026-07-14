# sMRI Pipeline Environment Notes

The new conda environment name should be:

```bash
cd <PIPELINE_DIR>
conda env create -f environment/environment.yml
conda activate sMRI_pipeline_win
```

The copied nnU-Net source tree and old document indicate nnU-Net v1 style commands. The prediction command shape is:

```bash
nnUNet_predict -i <BATCH_DIR>/2_nnunet_input/imagesTs \
  -o <BATCH_DIR>/2_nnunet_output \
  -m 3d_fullres \
  -t 523
```

`scripts/jobs/nnunet_task523.sh` will set these paths automatically if the resources directory is inside the project root:

```text
sMRI_pipelineV2/
  bin/
  scripts/
  resources/models/nnUNet/nnUNetData
```

During the transition, the job also falls back to the older sibling layout:

```text
<project-parent>/sMRI_pipelineV2
<project-parent>/resources/models/nnUNet/nnUNetData
```

If your cluster layout is different, export the v1 paths in the login shell or inside the Slurm job environment before submitting:

```bash
export nnUNet_raw_data_base=<PIPELINE_DIR>/resources/models/nnUNet/nnUNetData/nnUNet_raw_data_base
export nnUNet_preprocessed=<PIPELINE_DIR>/resources/models/nnUNet/nnUNetData/nnUNet_preprocessed
export RESULTS_FOLDER=<PIPELINE_DIR>/resources/models/nnUNet/nnUNetData/RESULTS_FOLDER
```

Alternatively, set only:

```bash
export NNUNET_RESOURCE_DIR=<PIPELINE_DIR>/resources/models/nnUNet
```

and the job will derive the three nnU-Net v1 variables from `NNUNET_RESOURCE_DIR/nnUNetData`.

Check the environment before submitting real work:

```bash
which python
python --version
python -c "import pandas, numpy, nibabel, SimpleITK; print('sMRI python ok')"
which nnUNet_predict
nnUNet_predict --help | head
echo "$nnUNet_raw_data_base"
echo "$nnUNet_preprocessed"
echo "$RESULTS_FOLDER"
```

FSL/ANTs/FreeSurfer/Workbench are not fully captured here yet. Stage 1 registration still uses the cluster FSL setup from `scripts/jobs/sMRI_pipeline_step0_reg2_v2.sh` and the existing `scripts/jobs/reg2.sh`; ACPC and recon container boundaries will be designed after the mask-all layer is stable.

## ACPC / preprocessing jobs

`bin/smri_preprocessing.sh --submit` is a login-node orchestration script. It should be run with `bash`, not `sbatch`.
It submits heavy jobs with `sbatch`, waits for them from the console using `squeue`/`sacct`, and then runs lightweight glue steps locally:

```text
local: rename, age suffix, nnU-Net input
sbatch: registration + nnU-Net
sbatch by default: mask_all after registration + nnU-Net dependency
local: split 3_skullstrip -> 4_results
sbatch: ACPC T1T2 first, then justT1 if present
sbatch: ACPC QC after each branch
local after wait: Fail/Questionable selection
sbatch: denoise, submitted as a long independent GPU job
local: final report
```

This keeps split and selection out of the Slurm queue by default. `mask_all` defaults to Slurm because the script keeps a strict dependency on registration + nnU-Net, but the adjacent local fallback block in `bin/smri_preprocessing.sh` can be uncommented if the cluster allows login-node NIfTI I/O.
The polling interval defaults to 60 seconds and can be changed with:

```bash
export SMRI_POLL_SECONDS=120
```

The ACPC wrapper keeps the old algorithm script and only parameterizes paths:

```bash
export SMRI_ACPC_SCRIPT=<PIPELINE_DIR>/scripts/legacy/preprocessing_ttl_v1.sh
export SMRI_TEMPLATE_DIR=/public_bme/data/zhanghan_group/sMRI_pipeline_new/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0/
export SMRI_ACPC_JOBS=20
export SMRI_WORKBENCH_BIN=/public_bme/home/zhanghan_group_public/software/workbench-linux64-v2.0.0/workbench/bin_linux64
export FREESURFER_HOME=/public/software/apps/freesurfer_infant/freesurfer/
```

Those defaults match the legacy script. For containerization, these become bind-mounted resources or image paths.

## moAR-diff denoise boundary

Questionable and Fail subjects are copied to:

```text
<BATCH_DIR>/5_questionable/raw/<subject>
<BATCH_DIR>/5_questionable/input/<subject>/T1.nii.gz
<BATCH_DIR>/5_questionable/output/<subject>/T1_age.nii.gz
<BATCH_DIR>/5_questionable/final/<subject>/T1_acpc.nii.gz
```

`raw/<subject>` keeps the original ACPC output. `input/<subject>/T1.nii.gz` is a model-specific working copy created from `T1_acpc.nii.gz`. The current BCP ACPC grid is `243x291x198`, while moAR-diff expects `192x240x192`, so the selection step crops the foreground bounding box and center-pads it to `192x240x192` before denoise. This resize only modifies `5_questionable/input`; it must not overwrite `raw`, `4_results`, or `3_skullstrip`.

The denoise job is submitted as a separate long GPU job and the main preprocessing chain does not wait for it to finish. Track it with:

```bash
cat <BATCH_DIR>/manifests/denoise_job_id.txt
squeue -j <job_id>
```

The current wrapper is `scripts/jobs/denoise_moardiff.sh`. It records `21_denoise_summary.csv`.
Before real inference, validate the moAR-diff environment, then optionally export:

```bash
export MOARDIFF_DIR=<PIPELINE_DIR>/resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune
export MOARDIFF_CKPT=$MOARDIFF_DIR/exp/logs/finetuneDPM_with_age/ckpt_100000.pth
export SMRI_DENOISE_CONDA_SH=/path/to/miniconda/etc/profile.d/conda.sh
export SMRI_DENOISE_CONDA_ENV=sMRI_pipeline_win
```

If using Singularity/Apptainer instead of conda:

```bash
export SMRI_DENOISE_CONTAINER=/path/to/smri_denoise.sif
export SMRI_DENOISE_BIND_ARGS="-B /public_bme2:/public_bme2"
```

The job uses `--nv` for GPU access. The wrapper checks imports and `torch.cuda.is_available()` before running model inference.

## Postprocessing / FreeSurfer boundary

`bin/smri_presurf_recon.sh --submit` is the second entrypoint:

```bash
bash <PIPELINE_DIR>/bin/smri_presurf_recon.sh <BATCH_DIR> --submit
```

It expects manual segmentation results under:

```text
<BATCH_DIR>/6_seg/<subject>/brain.nii.gz
<BATCH_DIR>/6_seg/<subject>/dk-struct.nii.gz
<BATCH_DIR>/6_seg/<subject>/tissue.nii.gz
```

It submits:

```text
presurf.sh -> recon_all.sh
```

The data paths are parameterized to `<BATCH_DIR>/6_seg` and `<BATCH_DIR>/7_presurf`. These environment/resource paths are intentionally still external and must be checked on the cluster before full one-click deployment:

```bash
module load tools/parallel/20200122
module load apps/fsl/6.0
module load apps/ants
export FREESURFER_HOME=/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/FS8.1
export FS_LICENSE=/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/license.txt
```

Future one-station work: copy or bind FreeSurfer, the license, FSL/ANTs, and any infant recon templates into `resources/` or a Singularity image boundary, then replace these defaults with portable config.


