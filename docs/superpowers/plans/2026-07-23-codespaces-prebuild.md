# Codespaces Prebuild Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a no-MCR FreeSurfer Demo image that GitHub Codespaces can prebuild and run directly.

**Architecture:** A cloud-specific Dockerfile flattens FreeSurfer 8.1 into a fresh Rocky Linux stage while excluding `MCRv97`. The `demo` branch devcontainer uses the published image directly, and the existing Linux launchers call existing jobs without nested Docker.

**Tech Stack:** Docker BuildKit, Rocky Linux 8, FreeSurfer 8.1, dcm2niix, Bash, Python 3, GitHub Codespaces Prebuild.

## Global Constraints

- Modify only the `demo` branch.
- Do not alter FreeSurfer reconstruction algorithms.
- Do not stop container `45c7c3029c97`.
- Do not commit `.secrets/`, `cloud_data/`, medical data, or the user files `research_direction_decision/` and `t2-policy.patch`.
- Use one subject, one reconstruction job, and four threads for cloud validation.

---

### Task 1: Lock The Cloud Image Contract

**Files:**
- Modify: `tests/test_demo_pipeline.py`

**Interfaces:**
- Consumes: Dockerfile and devcontainer text.
- Produces: regression tests for the image tag, MCR exclusion, required tools, and direct Linux launchers.

- [ ] Add a test requiring `.devcontainer/devcontainer.json` to reference `caibility1/smri_pipeline_demo:cloud-nomcr-v1-2026-07-23`.
- [ ] Add a test requiring `docker/Dockerfile.smri-demo-cloud` to flatten FreeSurfer with BuildKit and exclude `MCRv97`.
- [ ] Add a test forbidding `fs_install_mcr` and nested-Docker features.
- [ ] Run `python -m unittest tests.test_demo_pipeline.CodespacesEntrypointTests -v` and observe failure before implementation.

### Task 2: Build The No-MCR Runtime

**Files:**
- Create: `docker/Dockerfile.smri-demo-cloud`
- Create: `docker/build_demo_cloud_image.ps1`
- Create: `docker/publish_demo_cloud_image.ps1`

**Interfaces:**
- Consumes: `freesurfer/freesurfer:8.1.0`, `caibility1/smri_pipeline_win:full-2026-07-15`, and repository build context.
- Produces: local image `smri_pipeline_demo:cloud-nomcr-test` and release image `caibility1/smri_pipeline_demo:cloud-nomcr-v1-2026-07-23`.

- [ ] Use `RUN --mount=from=freesurfer-source` to copy `/usr/local/freesurfer/8.1.0-1` while excluding `MCRv97`.
- [ ] Install only runtime OS packages already required by the official image plus Python.
- [ ] Copy dcm2niix and the repository, preserve FreeSurfer environment variables, and verify required commands during build.
- [ ] Build the image and run `docker/demo_entrypoint.sh doctor` with a mounted license.
- [ ] Inspect the image filesystem and assert that `MCRv97` is absent.

### Task 3: Point Codespaces At The Prebuild Runtime

**Files:**
- Modify: `.devcontainer/devcontainer.json`
- Modify: `.devcontainer/post_create.sh`
- Modify: `docs/codespaces_student_tutorial.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: published cloud image.
- Produces: a direct devcontainer with a deterministic post-create health check and student commands.

- [ ] Update the devcontainer image tag without adding Docker features or hard machine filters.
- [ ] Make post-create report CPU, RAM, disk, required tools, license state, and the exact next command.
- [ ] Document that Prebuild removes setup time but does not guarantee a 32 GB machine.
- [ ] Run all Demo unit tests.

### Task 4: Publish And Prebuild

**Files:**
- No repository file changes after publication metadata is committed.

**Interfaces:**
- Consumes: verified local image and pushed `demo` branch.
- Produces: Docker Hub release tag and completed GitHub Codespaces Prebuild.

- [ ] Push `caibility1/smri_pipeline_demo:cloud-nomcr-v1-2026-07-23`.
- [ ] Commit and push the tested repository changes to `origin/demo`.
- [ ] Configure a Codespaces Prebuild for branch `demo`, region Southeast Asia, using the available 4-core machine.
- [ ] Wait for the prebuild workflow to finish and record any quota or storage error verbatim.

### Task 5: Run One Isolated Cloud Case

**Files:**
- Test output only under ignored `cloud_data/` and `.secrets/`.

**Interfaces:**
- Consumes: prebuilt Codespace and de-identified `DEMO001` T1/T2 files.
- Produces: `recon-all.done`, pial surfaces, reconstruction summary, and STL files.

- [ ] Create a fresh Codespace from the completed prebuild.
- [ ] Upload the prepared de-identified archive and unpack it inside ignored directories.
- [ ] Run `.devcontainer/post_create.sh` and verify all required tools.
- [ ] Run `./bin/smri_reconstruction.sh "$PWD/cloud_data/MRI_CLASS" --submit --skip-dicom --subject DEMO001 --recon-jobs 1 --recon-threads 4`.
- [ ] Wait for completion and verify `surf/lh.pial`, `surf/rh.pial`, `mri/brainmask.mgz`, and `mri/aseg.mgz`.
- [ ] Run `./bin/smri_3d_print.sh "$PWD/cloud_data/MRI_CLASS" --subject DEMO001` and verify all three STL files are nonempty.

## Execution Note

Local no-MCR build and smoke tests passed at 10.77 GB. Publication is deferred
because the new 11.38 GB layer would take roughly 18 hours at the measured
uplink. Tasks 4 and 5 use the existing published `slim-v2.2-2026-07-23` image
for the first Prebuild reliability test; this does not change reconstruction
logic.