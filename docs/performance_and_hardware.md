# Hardware and Performance Guide

This guide helps decide whether a PC can run the pipeline and how to choose parallelism.

## 1. Practical Minimums

For learning and one-subject smoke tests:

- Windows 10/11 64-bit.
- 16-32 GB RAM.
- SSD storage.
- 100 GB free space if FreeSurfer/Docker are not both installed locally.
- NVIDIA GPU is strongly preferred for nnU-Net/moAR-Diff, but CPU-only smoke tests may be possible for limited checks.

For real local processing:

- 64 GB RAM recommended.
- 150-250 GB free space recommended.
- NVIDIA GPU with 8 GB or more VRAM recommended.
- CPU with 8 cores / 16 threads or better.

For classroom use next week:

- Best: one prepared workstation or prepared WSL/Docker image.
- Risky: asking every beginner to install FSL, FreeSurfer, CUDA, and Docker from scratch.
- Avoid: low-end integrated-graphics laptops for full nnU-Net/moAR-Diff processing.

## 2. Disk Space Planning

Approximate sizes:

| Component | Approximate size |
| --- | ---: |
| Repository without large resources | < 1 GB |
| Models/templates included in this branch | 2-5 GB |
| Windows conda environment | 3-8 GB |
| WSL Ubuntu and packages | 10-25 GB |
| FSL | 10-20 GB |
| FreeSurfer | 10-25 GB |
| Docker AI image | 8-20 GB |
| Docker tools image before FSL/FreeSurfer | 5-20 GB |
| One subject intermediate outputs | several GB |
| One subject FreeSurfer outputs | often several GB |

Recommendation:

- Small WSL-only test: reserve 100-150 GB.
- WSL + Docker + FreeSurfer development machine: reserve 250 GB or more.
- Batch processing: plan extra space per subject and clean failed intermediate attempts deliberately.

## 3. Stage-by-Stage Hardware Use

| Stage | Default backend | Main dependency | GPU needed | Parallel control |
| --- | --- | --- | --- | --- |
| File standardization, manifests, reports | Windows Python | pandas/openpyxl/nibabel | No | None |
| T2-to-T1 registration | WSL2 | FSL | No | Internal shell/GNU parallel |
| nnU-Net skull stripping | WSL2 | nnU-Net/PyTorch/CUDA | Yes, recommended | No user-facing parallel flag |
| mask_all | Windows Python | nibabel/SimpleITK | No | None |
| ACPC/QC | WSL2 | FSL/ANTs/Workbench | No | `--acpc-jobs` |
| moAR-Diff denoise | WSL2 | PyTorch/CUDA | Yes, recommended | Usually single process |
| presurf | Windows Python | nibabel/SimpleITK | No | None |
| infant FreeSurfer recon | WSL2 | FreeSurfer | No | `--recon-jobs` |

## 4. Low-End GPU, CPU, and Integrated Graphics

### NVIDIA MX450 2 GB

Not recommended for nnU-Net/moAR-Diff production. A 2 GB GPU can be useful for display or small CUDA tests, but 3D medical imaging models and diffusion denoising can easily run out of VRAM.

### AMD Ryzen CPU

Good enough for CPU stages and FreeSurfer, depending on core count and RAM. It can run Python, FSL, ANTs, Workbench, and FreeSurfer. It is not a practical replacement for NVIDIA GPU inference in nnU-Net/moAR-Diff.

### AMD/Intel Integrated Graphics

Not a CUDA GPU. Current PyTorch CUDA, nnU-Net, and moAR-Diff paths require NVIDIA CUDA for GPU acceleration. Integrated graphics may run the desktop, but it should not be counted as model acceleration for this pipeline.

### CPU-only nnU-Net/moAR-Diff

Use only for smoke tests if a script explicitly allows it. It may be extremely slow and is not recommended for real batches.

References:

- PyTorch install selector: https://pytorch.org/get-started/locally/
- NVIDIA CUDA: https://developer.nvidia.com/cuda-zone
- CUDA on WSL: https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl
- nnU-Net installation: https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/installation_instructions.md

## 5. Parallelism Rules

`--acpc-jobs` controls how many subjects ACPC processes at the same time:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --acpc-jobs 2
```

`--recon-jobs` controls how many subjects FreeSurfer reconstructs at the same time:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> --submit --recon-jobs 2
```

Suggested values:

| RAM | ACPC | FreeSurfer recon |
| --- | --- | --- |
| 16 GB | `--acpc-jobs 1` | `--recon-jobs 1` |
| 32 GB | `--acpc-jobs 1-2` | `--recon-jobs 1-2` |
| 64 GB | `--acpc-jobs 2-4` | `--recon-jobs 2-4` |

If the machine freezes, WSL memory grows too much, or logs show memory errors, reduce the job count first.

## 6. Timing Expectations

Timing depends heavily on CPU, disk, GPU, and image size. On a capable workstation, rough order of magnitude can be:

- Registration: minutes per small batch.
- nnU-Net: minutes to tens of minutes depending on GPU and subject count.
- ACPC: minutes per subject, can parallelize.
- moAR-Diff: minutes per selected subject on a good GPU.
- FreeSurfer infant recon: often hours per subject.

For a new machine, benchmark with one subject first and record timing in a local deployment note.

## 7. Beginner-Friendly Recommendation

If a high-school student must deploy this next week, the most reliable setup is not “everything from scratch on any laptop.” It is:

1. Prepared Windows workstation.
2. Prepared WSL2 Ubuntu or a written WSL setup checklist.
3. Project folder already containing models/templates.
4. FreeSurfer license already obtained and placed in a known folder.
5. One small test batch.
6. `wsl_doctor.sh` used as the checklist before real runs.

A random low-end laptop with only integrated graphics can learn the command structure, but it should not be expected to complete full GPU denoising and segmentation efficiently.

