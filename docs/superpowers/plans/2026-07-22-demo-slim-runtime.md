# Teaching Demo Slim Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a FreeSurfer-only teaching image for DICOM conversion, standard reconstruction, and STL export.

**Architecture:** Base directly on FreeSurfer 8.1, add a pinned dcm2niix binary and minimal Python, copy demo code last, and remove the active FSL registration path.

**Tech Stack:** Docker, Rocky Linux/FreeSurfer 8.1, dcm2niix, Python 3 standard library, PowerShell, bash.

## Global Constraints

- Preserve DICOM candidate inventory and explicit selection behavior.
- Preserve standard recon-all, T2 pial policy, checkpoints, and STL outputs.
- Do not delete historical scripts.
- Do not include AI models or unrelated neuroimaging tool suites.
- Public tags are readable and versioned.

---

### Task 1: Define Slim Image Contracts

**Files:**
- Modify: `tests/test_demo_pipeline.py`

- [ ] Add failing tests that require a FreeSurfer base, reject the full Windows base and FSL requirements, and keep dcm2niix/recon-all/mris_convert checks.
- [ ] Replace active registration tests with a controller test that rejects or omits `--registration`.
- [ ] Run `python -m unittest discover -s tests -v` and confirm the new tests fail.
- [ ] Commit the contract tests.

### Task 2: Build the Minimal Runtime

**Files:**
- Modify: `docker/Dockerfile.smri-demo`
- Modify: `docker/demo_entrypoint.sh`
- Modify: `docker/build_demo_image.ps1`
- Modify: `docker/doctor_demo.ps1`

- [ ] Base on `freesurfer/freesurfer:8.1.0`.
- [ ] Install or copy pinned dcm2niix and ensure Python 3 is available.
- [ ] Keep code as the final small layer.
- [ ] Remove FSL from doctor and entrypoint checks.
- [ ] Build `smri_pipeline_demo:slim-test` and run doctor.
- [ ] Commit the slim runtime.

### Task 3: Remove Active Registration Routing

**Files:**
- Modify: `scripts/jobs/smri_reconstruction_demo.sh`
- Modify: `bin/smri_reconstruction.ps1`
- Modify: `README.md`
- Modify: `docs/teaching_demo_tutorial.md`

- [ ] Remove the active `--registration` option and references while retaining legacy files.
- [ ] Document that suitable T2 images are passed to FreeSurfer pial refinement.
- [ ] Verify DICOM-only, select-only, skip-DICOM, subject filtering, and STL command construction.
- [ ] Commit the workflow simplification.

### Task 4: Verify, Measure, and Publish

**Files:**
- Modify: `docker/publish_demo_image.ps1`
- Modify: `docs/teaching_day_runbook.md`

- [ ] Run all unit tests and shell syntax checks.
- [ ] Run DICOM conversion and selection smoke tests.
- [ ] Run one complete recon-all and STL export.
- [ ] Record compressed manifest size and local Docker footprint.
- [ ] Publish `slim-v2-2026-07-22`; update `latest` only after validation.
- [ ] Commit and push the demo slim branch.
