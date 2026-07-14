# sMRI Pipeline V2 Windows/WSL2

This repository is the Windows/WSL2 deployment branch of an sMRI preprocessing and infant FreeSurfer pipeline. It keeps the original algorithm scripts where possible, but replaces Linux-cluster Slurm submission with Windows PowerShell orchestration, WSL2 Linux tools, and optional Docker containers.

The goal is simple: a new user should be able to deploy the command-line pipeline, run one batch, and find the reports without reading source code.

## 1. User-Facing Commands

There are two main entrypoints:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> [options]
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> [options]
```

- `smri_preprocessing.ps1` runs data standardization, age suffix handling, T2-to-T1 registration, nnU-Net skull stripping, masking, ACPC alignment, ACPC QC summaries, and optional moAR-Diff denoising.
- `smri_presurf_recon.ps1` prepares segmentation outputs for FreeSurfer and runs infant recon.

Supporting scripts live under `scripts/jobs` and `scripts/steps`. Normal users should not need to run those directly.

## 2. Recommended New-Machine Path

For a new PC, use this order:

1. Install or verify Windows prerequisites: PowerShell, Git, Miniforge/conda, NVIDIA driver if a GPU exists.
2. Install or verify WSL2 Ubuntu 22.04.
3. Create the Windows conda environment `sMRI_pipeline_win`.
4. Install or verify Linux tools in WSL2: FSL, ANTs, Workbench, FreeSurfer, and a FreeSurfer license.
5. Put model resources under `resources/models`.
6. Optional: install Docker Desktop and pull/build `smri_pipeline_win:ai` and `smri_pipeline_win:tools`.
7. Run doctor/smoke tests before a full batch.
8. Run preprocessing, then run presurf/recon after `6_seg` exists.

Start with: [New machine tutorial](docs/new_machine_tutorial.md).

## 3. What Docker Solves

Docker is useful for reproducible runtime environments. It does not remove every manual step.

Docker can provide:

- `smri_pipeline_win:ai`: CUDA/PyTorch, nnU-Net v1 runtime, moAR-Diff dependencies.
- `smri_pipeline_win:tools`: Linux utility runtime, ANTs/support packages, and wrappers that can use mounted tools.
- Consistent command execution through the same PowerShell entrypoints.

Usually still manual or institution-specific:

- Windows NVIDIA driver and Docker Desktop WSL2/GPU integration.
- FreeSurfer license.
- Whether FSL/FreeSurfer are installed in WSL, mounted into Docker, or baked into a private internal image.
- Private model checkpoints if they cannot be redistributed.
- Local batch data location.

Read: [Docker deployment guide](docs/windows_docker_deployment_guide.md) and [Containerization strategy](docs/containerization_strategy.md).

## 4. Data Modes

### Known internal datasets with visual QC

Use this when you have a CBCP/ASD/SHCH-style QC workbook with subject ID, age, and T1 visual QC status.

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL.xlsx>
```

The pipeline reads age from the workbook and selects `fail` / `questionable` T1 cases for denoising.

### External data with age but no visual QC

Use this when the new dataset only has age information, or when every case should be treated as pass for visual QC.

If subject folders already include age:

```text
<BATCH_DIR>\1_T2toT1\data\subject001_24mo\T1.nii.gz
```

run:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --age-source folder `
  --qc-mode all-pass
```

If age is in a simple Excel file, use columns such as `subject_id` and `age` or `month`:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <AGE_TABLE.xlsx> `
  --age-source excel `
  --qc-mode all-pass
```

The ID matching is tolerant of Excel dropping leading zeros for numeric IDs.

## 5. Expected Batch Layout

Preprocessing input:

```text
<BATCH_DIR>\
  1_T2toT1\
    data\
      <subject_id>\
        T1.nii.gz
        T2.nii.gz   # optional
```

Postprocessing input after segmentation:

```text
<BATCH_DIR>\
  6_seg\
    <subject_id>\
      brain.nii.gz
      dk-struct.nii.gz
      tissue.nii.gz
```

Data stays outside Docker images. The launcher mounts `<BATCH_DIR>` into containers at runtime.

## 6. Quick Commands After Deployment

Load local env:

```powershell
cd <PIPELINE_DIR>
conda activate sMRI_pipeline_win
. .\environment\windows_env.local.ps1
```

If Docker is used:

```powershell
. .\environment\docker_env.local.ps1
```

Run preprocessing with visual QC:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --qc-excel <QC_EXCEL.xlsx>
```

Run preprocessing for external age-only data:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --qc-excel <AGE_TABLE.xlsx> --age-source excel --qc-mode all-pass
```

Run postprocessing/recon after `6_seg` exists:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> --submit --recon-jobs 2
```

Use `--recon-jobs 1` on weak machines.

## 7. Logs and Reports

- Preprocessing report: `<BATCH_DIR>\logs\preprocessing_report.md`
- Postprocessing report: `<BATCH_DIR>\logs\postprocessing_report.md`
- Step status CSV: `<BATCH_DIR>\manifests\windows_status.csv`
- FreeSurfer log: `<BATCH_DIR>\7_presurf\<subject_id>\log\recon.log`

## 8. Documentation Map

- [New machine tutorial](docs/new_machine_tutorial.md)
- [Windows/WSL2 deployment guide](docs/windows_deployment_guide.md)
- [Docker deployment guide](docs/windows_docker_deployment_guide.md)
- [Command reference](docs/command_reference.md)
- [Full test runbook](docs/full_test_runbook.md)
- [Hardware and performance](docs/performance_and_hardware.md)
- [Containerization strategy](docs/containerization_strategy.md)

