# Command Reference

Use this page after the deployment tutorial is complete. It explains what each command option means without requiring source-code reading.

## 1. Preprocessing

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> [options]
```

Typical full run:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL.xlsx>
```

### Main Run Modes

- `--submit`: run heavy preprocessing steps instead of only preparation/checking.
- `--stage1-only`: stop after registration, nnU-Net, and mask generation.
- `--acpc-start`: resume from ACPC preparation/alignment.
- `--denoising-start`: resume from questionable/fail selection and denoising.
- `--denoising`: run denoising using existing `5_questionable\input`.
- `--run-maskall-local`: rerun only local mask_all logic.
- `--no-denoise-submit`: select denoise candidates but do not run moAR-Diff.
- `--dry-run`: write logs and generated commands without executing heavy jobs.

Only one resume mode should be used at once: `--acpc-start`, `--denoising-start`, or `--denoising`.

### Data and Resource Options

- `--qc-excel <xlsx>`: age/QC spreadsheet. For CBCP/ASD/SHCH-style datasets it can provide both age and visual QC status. For external datasets it may contain only ID and age columns when used with `--qc-mode all-pass`.
- `--nnunet-resource-dir <dir>`: nnU-Net resource root. Default: `resources\models\nnUNet`.
- `--nnunet-task-name <id>`: nnU-Net task name/id. Default: `523`.
- `--age-source <auto|excel|folder>`: age source. `auto` uses Excel if available, otherwise existing folder suffixes like `subject001_24mo`; `excel` requires an age/QC Excel; `folder` requires folders already ending in `_<age>mo`.
- `--qc-mode <visual|all-pass>`: visual QC mode. `visual` reads T1 QC status from Excel and selects fail/questionable cases for denoising. `all-pass` treats all ACPC outputs as pass and skips denoise candidate selection, useful for external data without visual QC.
- `--moardiff-dir <dir>`: moAR-Diff model folder.
- `--moardiff-checkpoint <path>`: moAR-Diff checkpoint file.
- `--moardiff-config-name <file>`: moAR-Diff config name. Default: `inference.yml`.
- `--template-dir <dir>`: ACPC/template resource directory.

### Backend Options

Backend values are `windows`, `wsl`, `docker`, or `skip`, but not every step supports every backend.

- `--registration-backend`: FSL registration. Recommended: `wsl` or `docker`.
- `--nnunet-backend`: nnU-Net skull stripping. Recommended: `wsl`; `docker` after Docker setup; `windows` only if Windows CUDA/PyTorch works.
- `--mask-backend`: mask_all. Default: `windows`.
- `--acpc-backend`: FSL/ANTs/Workbench ACPC. Recommended: `wsl` or `docker`.
- `--denoise-backend`: moAR-Diff. Recommended: `wsl`; `docker` after Docker GPU setup; `windows` only if Windows CUDA/PyTorch works.

### Parallelism and Runtime Options

- `--acpc-jobs <N>`: ACPC subject parallelism. Default: `4`.
- `--wsl-distro <name>`: WSL distribution name. Example: `Ubuntu-22.04`.
- `--python-bin <path>`: Windows Python executable. Default: current `python`.
- `--docker-tools-image <name>`: tools container image. Default: `smri_pipeline_win:tools`.
- `--docker-ai-image <name>`: AI container image. Default: `smri_pipeline_win:ai`.
- `--docker-gpus <value>`: Docker GPU setting. Use `all` for NVIDIA GPU containers; `none` for CPU-only smoke tests.

## 2. Presurf and Recon

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> [options]
```

Typical full run:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --recon-jobs 2
```

### Main Run Modes

- `--submit`: run presurf and FreeSurfer recon.
- `--presurf-only`: prepare `7_presurf` inputs, then stop before FreeSurfer.
- `--dry-run`: write logs/commands without executing heavy jobs.

`--Qsubmit` is intentionally disabled. Denoised/questionable images must be segmented first and placed into a valid `6_seg` layout before standard postprocessing.

### Backend and FreeSurfer Options

- `--presurf-backend`: default `windows`; presurf is lightweight Python/file preparation.
- `--recon-backend`: default `wsl`; FreeSurfer requires Linux/WSL or Docker.
- `--freesurfer-home <dir>`: FreeSurfer install directory, or set `FREESURFER_HOME`.
- `--fs-license <path>`: FreeSurfer license file, or set `FS_LICENSE`.
- `--recon-jobs <N>`: number of subjects reconstructed at the same time. `--recon-jobs 2` means two subjects in parallel.
- `--docker-tools-image <name>`: Docker tools image. Default: `smri_pipeline_win:tools`.
- `--docker-gpus <value>`: Docker GPU setting. Recon usually does not need GPU; default `none` is fine.

## 3. How to Read Runtime Output

Every major step prints:

```text
>>> START <step> [<backend>]
    log: <log path>
<<< COMPLETE <step> [<backend>] rc=0 elapsed=<time>
```

If a step fails:

```text
<<< FAILED <step> [<backend>] rc=<nonzero> elapsed=<time>
    check log: <log path>
```

The same status is appended to:

```text
<BATCH_DIR>\manifests\windows_status.csv
```

FreeSurfer writes detailed per-subject logs here:

```powershell
Get-Content <BATCH_DIR>\7_presurf\<subject_id>\log\recon.log -Tail 50
```

## 4. Safe First Commands

Check help:

```powershell
.\bin\smri_preprocessing.ps1 --help
.\bin\smri_presurf_recon.ps1 --help
```

Dry-run preprocessing with a visual QC table:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --dry-run --qc-excel <QC_EXCEL.xlsx>
```

Dry-run preprocessing for external data with age already in folder names and no visual QC table:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --dry-run --age-source folder --qc-mode all-pass
```

Prepare presurf only:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> --submit --presurf-only
```



