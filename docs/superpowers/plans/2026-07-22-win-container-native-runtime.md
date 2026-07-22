# Windows Container-Native Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the full Windows pipeline through one self-contained Docker runtime without host conda or setup.

**Architecture:** Copy active pipeline code into the full image, add a container entrypoint, add a native backend to existing dispatchers, and reduce host launchers to Docker mount/dispatch wrappers.

**Tech Stack:** PowerShell, CMD, Python 3.10, bash, Docker BuildKit, FSL, ANTs, FreeSurfer, Workbench, nnU-Net v1, PyTorch, MoAR-Diff.

## Global Constraints

- Preserve Linux cluster entrypoints and algorithm behavior.
- Do not delete legacy setup or scripts.
- Batch data and outputs remain on the host.
- Runtime must not require host conda or a separate Ubuntu distribution.
- Public tags are readable and versioned.

---

### Task 1: Define Runtime Contracts

**Files:**
- Modify: `tests/test_portable_docker_files.py`
- Modify: `tests/test_windows_entrypoints.py`

- [ ] Add failing tests for code copied to `/opt/smri/pipeline`, a runtime entrypoint, native backend support, PS1 launchers without host Python, and CMD companions.
- [ ] Run `python -m unittest tests.test_portable_docker_files tests.test_windows_entrypoints -v` and confirm the new tests fail.
- [ ] Commit the tests.

### Task 2: Add Container Native Execution

**Files:**
- Modify: `scripts/steps/smri_windows_utils.py`
- Modify: `scripts/jobs/smri_preprocessing_win.py`
- Modify: `scripts/jobs/smri_presurf_recon_win.py`
- Create: `docker/runtime_entrypoint.sh`

- [ ] Add `native` to backend parsing and implement direct bash execution with exported environment variables.
- [ ] Route registration, nnU-Net, masking, ACPC, denoise, presurf, and recon jobs through native execution when inside the runtime.
- [ ] Implement entrypoint commands `preprocess`, `postprocess`, `doctor`, and `help`.
- [ ] Run dispatcher unit tests and shell syntax checks.
- [ ] Commit native execution.

### Task 3: Build the Runtime Image

**Files:**
- Modify: `docker/Dockerfile.smri-full-portable`
- Create: `docker/build_runtime_image.ps1`
- Create: `docker/publish_runtime_image.ps1`

- [ ] Copy active code after stable tool/model layers so code-only releases produce a small pull.
- [ ] Set `PIPELINE_DIR`, `FS_LICENSE`, native backend defaults, Python, and entrypoint.
- [ ] Add readable version labels and a release manifest.
- [ ] Build a local `smri_pipeline_win:runtime-test` image and run `doctor`.
- [ ] Commit runtime image support.

### Task 4: Replace Host Orchestration

**Files:**
- Modify: `bin/smri_preprocessing.ps1`
- Modify: `bin/smri_presurf_recon.ps1`
- Create: `bin/smri_preprocessing.cmd`
- Create: `bin/smri_presurf_recon.cmd`

- [ ] Build Docker arguments for batch, license, external QC workbook, GPU, and runtime image.
- [ ] Preserve all user-facing pipeline arguments.
- [ ] Remove runtime dependence on local environment files and host Python.
- [ ] Verify `--help` works without conda and test Windows path quoting.
- [ ] Commit host launchers.

### Task 5: Verify and Publish

**Files:**
- Modify: `README.md`
- Modify: `docs/portable_docker_tutorial.md`
- Modify: `docs/command_reference.md`

- [ ] Run the complete unit suite.
- [ ] Run image doctor and smoke commands with host conda variables removed.
- [ ] Run one representative preprocessing and postprocessing test without nested Docker.
- [ ] Publish `runtime-v2-2026-07-22`; update `latest` only after validation.
- [ ] Document direct Docker and launcher workflows and the old rollback tag.
- [ ] Commit and push the release branch.
