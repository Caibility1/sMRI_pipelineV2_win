# Containerization Strategy

This page explains what Docker can and cannot solve for the Windows/WSL2 sMRI pipeline.

## 1. Short Answer

Yes, the pipeline can be partially containerized. The most practical architecture is hybrid:

```text
Windows PowerShell entrypoint
  -> Windows Python lightweight steps
  -> WSL2 or Docker Linux runtime for heavy/Linux-only steps
  -> mounted project code, mounted data, mounted resources/models
```

Do not put the whole user workflow inside one opaque container at the beginning. Keep the two `bin/*.ps1` entrypoints as the user interface.
## 1.1 Image, Container, and Mount

A Docker image is a reusable software environment template. In this project the image repository is named `smri_pipeline_win`, with tags such as:

```text
smri_pipeline_win:ai
smri_pipeline_win:tools
```

A Docker container is a running process created from an image. It is not the long-term storage place for the code repository. Containers are disposable: start, run a command, write outputs to mounted folders, then exit.

A mount connects a host folder to a path inside the container. For this pipeline, the command builder mounts:

```text
<PIPELINE_DIR> -> /pipeline
<BATCH_DIR>    -> /batch
```

So the container reads code from `/pipeline` and writes batch outputs under `/batch`, while the real files remain on Windows/WSL storage.

There are three possible code-distribution models:

1. Local repository mount: every PC has a copy of the repository and mounts it into containers. This is easiest to debug and is the current default.
2. Code baked into image: the image contains a copy of the pipeline code. Then each PC does not need a full source checkout, but updating code requires rebuilding/pulling a new image. Data still must be mounted.
3. Network/shared repository mount: PCs mount a shared network folder into Docker. This can work in an institution, but permissions, speed, privacy, and Docker Desktop file sharing must be managed carefully.

For development and teaching, use model 1. For hospital deployment, model 2 can become attractive after the pipeline stabilizes. Model 3 is possible but needs IT support.

## 2. What Docker Can Standardize Well

Good container targets:

- Python package versions for Linux jobs.
- PyTorch/CUDA runtime for nnU-Net and moAR-Diff.
- ANTs and GNU parallel if installed in the tools image.
- Runtime environment variables for nnU-Net and moAR-Diff.
- Reproducible command execution for registration, ACPC, denoise, and recon wrappers.

Existing planned images:

```text
smri_pipeline_win:ai
  PyTorch/CUDA
  nnU-Net v1
  moAR-Diff Python dependencies

smri_pipeline_win:tools
  Python utilities
  ANTs / GNU parallel / Linux support packages
  Workbench-facing jobs through mounted project resources
```

## 3. What Usually Remains Manual or Site-Specific

Docker does not remove these requirements:

- NVIDIA driver on the Windows host.
- Docker Desktop with WSL2 backend and GPU support.
- Model checkpoints if they are private or large.
- FreeSurfer license.
- FreeSurfer redistribution decision.
- FSL redistribution/install decision.
- Data folder layout and privacy rules.

FreeSurfer and FSL deserve special handling because they are large, version-sensitive, and may have license or redistribution constraints. For teaching or a small lab, install them in WSL first. For a hospital, build a private internal image only after the license/distribution question is settled.

## 4. Recommended Containerization Levels

### Level 0: No Docker

Use Windows + WSL2 only. This is easiest to debug and should be the first successful path on a development machine.

### Level 1: AI Docker Only

Use Docker for nnU-Net and moAR-Diff, keep FSL/ANTs/FreeSurfer in WSL.

Pros:

- Standardizes the fragile PyTorch/CUDA environment.
- Avoids rebuilding FSL/FreeSurfer images.

Cons:

- Still requires WSL tool installation.
- Users must understand two runtimes.

### Level 2: AI Docker + Tools Docker

Use Docker for AI and most Linux tool steps. Mount project resources and data.

Pros:

- More reproducible across PCs.
- Better for training new users.

Cons:

- FSL/FreeSurfer still need either image inclusion or host mounts.
- Docker volume/path errors become the main failure mode.

### Level 3: Private Full Image

A private institutional image includes FSL, ANTs, Workbench, FreeSurfer, and maybe models.

Pros:

- Best one-command deployment after Docker installation.
- Most consistent across machines.

Cons:

- Very large image.
- Requires license review.
- Harder to update individual models/tools.
- Not ideal for public redistribution.

## 5. Recommended Plan for Next Week Teaching

For high-school or beginner users, use this plan:

1. Provide the repository as a zip or Git clone.
2. Provide models/resources as a separate zip if they are large/private.
3. Teach Windows + WSL2 deployment first.
4. Use `wsl_doctor.sh` as the pass/fail checklist.
5. Use Docker only after the WSL path is understood, or provide prebuilt private images.
6. Start with one test subject.

For a classroom, avoid asking each student to compile FreeSurfer/FSL. Either provide a prepared machine, a prepared WSL export, or a private Docker image.

## 6. Disk Space Estimates

Rough planning numbers:

| Component | Approximate space |
| --- | ---: |
| Repository without large resources | < 1 GB |
| Project models/templates in this branch | 2-5 GB, depending on included files |
| Windows conda environment | 3-8 GB |
| WSL Ubuntu base + packages | 10-25 GB |
| FSL install | 10-20 GB |
| FreeSurfer install | 10-25 GB |
| Docker AI image | 8-20 GB |
| Docker tools image | 5-20 GB before FSL/FreeSurfer |
| One subject intermediate outputs | variable; reserve several GB per subject |
| One subject FreeSurfer output | often several GB |

Practical recommendation: reserve at least 150 GB free for a small deployment and 250 GB or more for repeated tests with Docker and FreeSurfer outputs.

## 7. What the Current Docker Scaffold Already Does

The repository already has:

- `docker/Dockerfile.smri-ai`
- `docker/Dockerfile.smri-tools`
- `docker/environment-ai.yml`
- `docker/environment-tools.yml`
- `docker/container_env.sh`
- `docker/build_images.ps1`
- Docker backend options in the two Windows entrypoints.

Current validation status:

- `smri_pipeline_win:ai` builds and passes Docker GPU/PyTorch checks.
- A PowerShell-launched nnU-Net Task523 smoke test with `--nnunet-backend docker` succeeds.
- `smri_pipeline_win:tools` builds and includes ANTs through conda.
- Workbench is discovered from the mounted repository resources.
- FSL and FreeSurfer are not included in the default public tools image.

The scaffold is ready for controlled AI-Docker testing. It should not be presented as a finished one-click full neuroimaging deployment until FSL/FreeSurfer distribution or mounting is finalized.

## 8. What Still Needs Engineering Work

Before calling Docker deployment beginner-proof, finish these:

1. Use `docker/doctor.ps1` to check Docker, images, GPU, mounted resources, and visible tools inside containers.
2. Decide whether FSL is installed inside `smri_pipeline_win:tools` or mounted from a host path.
3. Decide whether FreeSurfer is installed inside a private image or mounted from a host path.
4. Add a documented model bundle layout and checksum list.
5. Add an import step for common raw data layouts, so external users do not need to manually create `1_T2toT1\data\subject\T1.nii.gz`.
6. Run a one-subject Docker smoke test before recommending Docker to beginners.

## 9. Suggested Default for Now

Use WSL2 as the official beginner path and Docker as an advanced reproducibility path.

That means the README should teach WSL2 first, then explain Docker as an optional layer. A future hospital package can ship prebuilt internal Docker images after license and size decisions are settled.





