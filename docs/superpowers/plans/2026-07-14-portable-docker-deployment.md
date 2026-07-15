# Portable Docker Deployment Implementation Record

**Goal:** Reduce a new Windows PC deployment to host prerequisites, a code clone, one all-in-one image pull/load, a FreeSurfer license, and one repeatable setup command.

**Final architecture:** Windows PowerShell remains the workflow interface. Batch data stays on the host. `smri_pipeline_win:full-portable` is configured as both the AI and tools backend and contains FSL, ANTs, FreeSurfer, Workbench, templates, nnU-Net/Task523, and moAR-Diff/checkpoint. Docker Desktop requires WSL2 system support, but the recommended mode does not require a separate Ubuntu user distribution.

## Completed

- [x] Route bundled container resources through `/opt/smri`, `/opt/fsl`, and `/opt/freesurfer` while preserving host/WSL fallbacks.
- [x] Add environment-driven Docker backend defaults to both Windows dispatchers.
- [x] Add `docker/Dockerfile.smri-full-portable` and keep optional split-image definitions for development.
- [x] Preserve FreeSurfer as the final base image layer instead of copying it into a redundant large layer.
- [x] Import the existing WSL FSL tree through a tar-backed Docker context image so Linux symlinks survive Windows BuildKit.
- [x] Add local build, publish/offline-save, install, doctor, and new-machine setup PowerShell scripts.
- [x] Add a lightweight Windows conda environment without PyTorch/nnU-Net duplication.
- [x] Keep the FreeSurfer license outside Git and outside the image; mount the ignored repository copy at runtime.
- [x] Make Ubuntu/FSL/ANTs/FreeSurfer installation in a user WSL distribution optional rather than required.
- [x] Document online GHCR and offline `docker save/load` deployment paths.
- [x] Build and smoke-test the full image with PyTorch/CUDA, FSL, ANTs, Workbench, FreeSurfer, both models, templates, and license.
- [x] Run the Python test suite and PowerShell/Bash/Python syntax checks.

## Release Operations Still Requiring Credentials Or A Target PC

- [ ] Push a versioned private GHCR tag after `docker login ghcr.io` with package write permission.
- [ ] Run `setup_new_machine.ps1` on a clean target PC using either the GHCR release or the generated offline archive.
- [ ] Run a user-controlled one-subject preprocessing test and, after valid `6_seg`, one-subject recon test.

## Constraints

- Never commit or bake `license.txt`, MRI data, or generated batch outputs into an image.
- Keep the Linux cluster entrypoints and Slurm workflow intact.
- Do not start long recon jobs automatically.
- Rebuild the image only when baked tools, environments, models, Workbench, or templates change; ordinary script updates use Git because the clone is mounted at `/pipeline`.
