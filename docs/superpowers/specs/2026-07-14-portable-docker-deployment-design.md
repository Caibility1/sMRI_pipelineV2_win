# Portable Docker Deployment Design

## Goal

Make a new Windows PC deploy the full sMRI pipeline through Git plus one private all-in-one Docker image. WSL2 supplies the Docker engine; Linux neuroimaging modules run inside the image.

## Selected Architecture

Keep the two PowerShell entrypoints as the only user-facing workflow. The host repository is cloned from GitHub and mounted read-only at `/pipeline`; batch data stays on the host and is mounted read-write at `/batch`.

Publish one versioned image under one private GHCR repository:

```text
ghcr.io/caibility1/smri_pipeline_win:full-<release>
```

The full image owns CUDA/PyTorch, nnU-Net and moAR-Diff with both models, FSL, ANTs, Workbench, infant FreeSurfer, and the UNC infant templates. The same image is configured as both the AI and tools backend. Image-owned resources live under /opt/smri, never under /pipeline.

## Alternatives Rejected

1. Runtime images plus a separate resource ZIP or Docker volume reduce image rebuilds, but add a second installer and more path state on every PC.
2. Separate portable AI and tools images reduce update size, but require users to understand two image roles. They remain available only as development alternatives.
3. WSL-installed tools mounted into Docker remain a supported development fallback, but do not meet the minimal new-machine goal.

## Host Requirements

The new PC still requires Windows 10/11, Git, WSL2 system support, Docker Desktop using its WSL2 engine, and an NVIDIA host driver for GPU stages. A small Windows conda environment runs the launchers and lightweight Python steps; it does not install PyTorch, CUDA, nnU-Net, or moAR-Diff.

The setup installs or verifies WSL2 system support for Docker Desktop; it does not require a separate Ubuntu user distribution, but it does not install FSL, ANTs, or FreeSurfer into the user distribution in the recommended mode. An old /root/fsl is ignored.

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

The all-in-one Dockerfile uses the official FreeSurfer 8.1 image as its final base layer, then adds the validated AI/tools environments, FSL 6.0.7.22, both models, Workbench, and templates. Keeping FreeSurfer as the base avoids copying it into a redundant 40+ GB layer. A PowerShell build/publish command creates a versioned full tag and supports both GHCR push and offline docker save/load.

The first private publication is built on the prepared development PC because the large/private resources are not in GitHub. Ordinary script changes do not require image rebuilds because code is mounted from the cloned repository. Docker images are rebuilt only when image dependencies or baked resources change.

Only nnU-Net, moAR-Diff, Workbench, and templates are copied from repository resources. Existing FreeSurfer/FSL backups under resources/software are ignored. Linux modules come from validated local/official image and FSL sources.

After pulling the images, the new-machine installer can restore the two models, Workbench, and templates into the clone's ignored `resources/` paths for WSL compatibility. Existing non-empty resources are preserved unless replacement is explicitly requested.

## New-Machine Installation Flow

The beginner-facing path is:

1. Enable WSL2 system support without a user distribution; install Git, Docker Desktop, NVIDIA driver if applicable, and Miniforge.
2. Start Docker Desktop and verify `docker version`.
3. Clone `https://github.com/Caibility1/sMRI_pipelineV2_win.git`.
4. Create the lightweight Windows conda environment from the repository.
5. Log in to `ghcr.io` with package read permission.
6. Run one repository installer that pulls the full release tag, restores the two models/Workbench/templates, and creates both local environment files.
7. Copy the user's FreeSurfer license to the ignored repository path used by Docker; copy to WSL only when that optional backend exists.
8. Do not install FSL/ANTs/FreeSurfer in Ubuntu unless deliberately using the advanced WSL fallback.
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
