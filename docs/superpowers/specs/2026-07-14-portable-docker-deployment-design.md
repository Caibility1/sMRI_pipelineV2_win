# Portable Docker Deployment Design

## Goal

Make a new Windows PC deploy the full sMRI pipeline through Git plus private GHCR images. Docker is the primary runtime; a repeatable WSL2 bootstrap installs fresh FSL, ANTs, and FreeSurfer only as a supported fallback.

## Selected Architecture

Keep the two PowerShell entrypoints as the only user-facing workflow. The host repository is cloned from GitHub and mounted read-only at `/pipeline`; batch data stays on the host and is mounted read-write at `/batch`.

Publish two versioned images under one private GHCR repository:

```text
ghcr.io/caibility1/smri_pipeline_win:ai-<release>
ghcr.io/caibility1/smri_pipeline_win:tools-<release>
```

The AI image owns the Linux Python/CUDA runtime, nnU-Net v1 model tree, and moAR-Diff source/checkpoint. The tools image owns FSL, ANTs, Workbench, infant FreeSurfer, and the UNC infant templates. Image-owned resources live under `/opt/smri`, never under `/pipeline`, so mounting the repository cannot hide them.

## Alternatives Rejected

1. Runtime images plus a separate resource ZIP or Docker volume reduce image rebuilds, but add a second installer and more path state on every PC.
2. One monolithic image gives one pull command, but duplicates unrelated CUDA/tool layers, makes every model or tool update very large, and conflicts with the existing per-stage AI/tools backends.
3. WSL-installed tools mounted into Docker remain a supported fallback, but do not meet the goal of minimal new-machine setup.

## Host Requirements

The new PC still requires Windows 10/11, Git, WSL2 Ubuntu 22.04, Docker Desktop using its WSL2 engine, and an NVIDIA host driver for GPU stages. A small Windows conda environment runs the launchers and lightweight Python steps; it does not install PyTorch, CUDA, nnU-Net, or moAR-Diff.

The WSL fallback ignores any old `/root/fsl`. It installs FSL into the ordinary WSL user's `$HOME/fsl`, ANTs into the pipeline WSL conda environment, and FreeSurfer 8.1 into `/usr/local/freesurfer/8.1.0`.

CPU-only deployment remains valid for lightweight and Linux-tool stages. nnU-Net and moAR-Diff may be allowed to run on CPU only as an explicit slow fallback; the doctor must clearly report when CUDA is unavailable.

## Resource Paths

Container defaults are fixed as follows:

```text
NNUNET_RESOURCE_DIR=/opt/smri/models/nnUNet
MOARDIFF_DIR=/opt/smri/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune
SMRI_TEMPLATE_DIR=/opt/smri/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0
SMRI_WORKBENCH_BIN=/opt/smri/workbench/bin_linux64
FSLDIR=/opt/fsl
FREESURFER_HOME=/opt/freesurfer
```

The three nnU-Net v1 variables are derived from `NNUNET_RESOURCE_DIR/nnUNetData`. Explicit command-line or environment overrides continue to work for development and cluster compatibility.

## License And Data Boundary

FreeSurfer software may be included only in a private image whose distribution is approved by the institution. `license.txt` is never copied into an image or committed to Git. The default host location is:

```text
<PIPELINE_DIR>\resources\software\freesurfer\license.txt
```

For this deployment, copy the same valid license to both:

```text
<PIPELINE_DIR>\resources\software\freesurfer\license.txt
/usr/local/freesurfer/license.txt
```

The first copy is mounted read-only into Docker; the second is used by WSL fallback jobs. Neither copy is committed or baked into an image. Raw MRI data, intermediate files, logs, reports, and reconstructed subjects remain under the user-provided absolute `<BATCH_DIR>` and are never included in images.

## Build And Publication

Full-image Dockerfiles copy only the resources relevant to their image. Dockerfile-specific ignore rules avoid sending FreeSurfer to the AI build or model checkpoints to the tools build. A PowerShell build/publish command validates required resource files, builds versioned local tags, logs in to GHCR through the normal Docker credential store, pushes both tags, and optionally maintains `ai-latest` and `tools-latest` aliases.

The first private publication is built on the prepared development PC because the large/private resources are not in GitHub. Ordinary script changes do not require image rebuilds because code is mounted from the cloned repository. Docker images are rebuilt only when image dependencies or baked resources change.

Only nnU-Net, moAR-Diff, Workbench, and templates are copied from repository resources into images. Existing FreeSurfer/FSL software backups under `resources/software` are ignored. The tools image installs FSL and FreeSurfer from official sources and installs ANTs from its pinned package environment.

After pulling the images, the new-machine installer can restore the two models, Workbench, and templates into the clone's ignored `resources/` paths for WSL compatibility. Existing non-empty resources are preserved unless replacement is explicitly requested.

## New-Machine Installation Flow

The beginner-facing path is:

1. Install Git, WSL2 Ubuntu 22.04, Docker Desktop, NVIDIA driver if applicable, and Miniforge.
2. Start Docker Desktop and verify `docker version`.
3. Clone `https://github.com/Caibility1/sMRI_pipelineV2_win.git`.
4. Create the lightweight Windows conda environment from the repository.
5. Log in to `ghcr.io` with package read permission.
6. Run one repository installer that pulls the two release tags, restores the two models/Workbench/templates, and creates `environment/docker_env.local.ps1`.
7. Copy the user's FreeSurfer license to the repository and WSL paths.
8. Optionally run the WSL bootstrap to install fresh FSL/ANTs/FreeSurfer fallback tools.
9. Run `docker/doctor.ps1`; all required checks must pass before a full batch.
10. Run the existing preprocessing and presurf/recon PowerShell entrypoints with Docker backends.

## Compatibility And Fallbacks

Existing local tags `smri_pipeline_win:ai` and `smri_pipeline_win:tools` remain usable. Existing WSL and host-mounted tool configurations remain supported for development. Linux cluster entrypoints and Slurm scripts are not replaced by the portable Docker release.

FSL may physically live at `$HOME/fsl`, `/opt/fsl`, or `/usr/local/fsl` in WSL when using the fallback backend, provided `FSLDIR` is correct. `/root/fsl` is not a supported beginner default because ordinary WSL users cannot reliably access the root home directory.

## Error Handling And Verification

The installer fails early on missing Docker, failed GHCR authentication, missing image tags, or insufficient disk space. The doctor verifies image presence, GPU visibility, Python imports, all three nnU-Net paths, the moAR checkpoint, templates, `flirt`, `N4BiasFieldCorrection`, `wb_command`, `recon-all`, `mri_convert`, `infant_recon_all`, and the mounted FreeSurfer license.

Verification is staged: static/unit tests, image-content smoke tests, a one-subject preprocessing test, and a one-subject postprocessing/recon submission controlled by the user. No automated test deletes user data or starts a long recon without explicit invocation.

## Documentation Deliverables

README becomes the short deployment index. A single new-machine Docker tutorial provides exact commands from zero to first test. Separate advanced pages retain WSL-only, custom mount, image publishing, troubleshooting, disk migration, and cluster instructions.
