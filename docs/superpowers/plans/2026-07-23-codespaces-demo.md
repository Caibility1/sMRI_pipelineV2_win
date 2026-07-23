# Codespaces Teaching Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browser-only GitHub Codespaces path for the existing teaching Demo.

**Architecture:** Codespaces starts the published slim Demo image directly and
mounts the `demo` branch as its workspace. Linux launchers delegate to the
existing job scripts, preserving the current algorithm and checkpoint behavior.

**Tech Stack:** GitHub Codespaces, Dev Containers, Docker Hub, Bash, FreeSurfer 8.1.

## Global Constraints

- Modify only the `demo` branch.
- Do not modify reconstruction algorithms or the Windows launchers.
- Use `caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23`.
- Require 8 CPUs, 32 GB RAM, and 64 GB storage.
- Do not upload identifiable DICOM during smoke testing.

---

### Task 1: Test The Cloud Configuration Contract

**Files:**
- Modify: `tests/test_demo_pipeline.py`

**Interfaces:**
- Consumes: repository text files.
- Produces: tests for the image reference, host requirements, Linux launchers,
  ignored data paths, and cloud tutorial.

- [ ] Add tests that read `.devcontainer/devcontainer.json`,
  `bin/smri_reconstruction.sh`, `bin/smri_3d_print.sh`, `.gitignore`, and
  `docs/codespaces_student_tutorial.md`.
- [ ] Run `python -m unittest discover -s tests -p "test_demo_pipeline.py" -v`
  and verify the new tests fail because the files do not exist.

### Task 2: Add The Dev Container And Linux Launchers

**Files:**
- Create: `.devcontainer/devcontainer.json`
- Create: `.devcontainer/post_create.sh`
- Create: `bin/smri_reconstruction.sh`
- Create: `bin/smri_3d_print.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the published slim image and existing scripts under `scripts/jobs/`.
- Produces: browser-hosted Linux runtime and stable command-line entrypoints.

- [ ] Add an image-based devcontainer with `overrideCommand`, required host
  resources, and a post-create health check.
- [ ] Add Bash launchers that set `PIPELINE_DIR` to the workspace repository and
  execute the existing reconstruction and STL job scripts.
- [ ] Ignore `cloud_data/` and `.secrets/`.
- [ ] Run the Demo unit tests and verify they pass.

### Task 3: Add The Student Tutorial

**Files:**
- Create: `docs/codespaces_student_tutorial.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the Codespaces deep link and Linux launchers.
- Produces: a linear browser-only student workflow.

- [ ] Document account creation, 8-core machine selection, file upload,
  `doctor`, DICOM inventory, candidate selection, reconstruction, STL download,
  quota monitoring, and Codespace deletion.
- [ ] Add the Codespaces link to the Demo README.
- [ ] Run the Demo unit tests and Markdown command-string checks.

### Task 4: Validate The Published Image As A Codespace Runtime

**Files:**
- Test only.

**Interfaces:**
- Consumes: current repository, FreeSurfer license, and published slim image.
- Produces: evidence that the image can run workspace Linux entrypoints.

- [ ] Mount the repository and license into the published image with
  `--entrypoint /bin/bash`.
- [ ] Run `.devcontainer/post_create.sh`,
  `bin/smri_reconstruction.sh --help`, and `bin/smri_3d_print.sh --help`.
- [ ] Validate `docker/demo_entrypoint.sh doctor`.
- [ ] Push the `demo` branch and create a real Codespace smoke test.
