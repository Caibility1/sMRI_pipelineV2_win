# Windows Container-Native Runtime Design

## Goal

Make the full Windows pipeline runnable with Docker Desktop alone after the host prerequisites are installed. The host must not need conda, Miniforge, Ubuntu packages, FSL, ANTs, FreeSurfer, Workbench, nnU-Net, MoAR-Diff, models, or templates.

## Compatibility

The existing Linux cluster entrypoints and algorithm scripts remain intact. The legacy hybrid Windows setup remains available as a rollback path and is fixed by tag `win-hybrid-backup-2026-07-22`.

## Runtime Architecture

The final image contains the repository runtime code at `/opt/smri/pipeline`, the AI Python environment, the tools environment, all models, FSL, ANTs, FreeSurfer, Workbench, and templates.

A container entrypoint exposes:

- `preprocess /data [options]`
- `postprocess /data [options]`
- `doctor`
- `help`

The entrypoint executes the existing Python dispatchers inside the container. A new native backend runs existing bash jobs directly instead of recursively invoking Docker or WSL.

## Host Interface

The Windows PS1 launchers remain and CMD companions are added. They only validate host paths, mount the batch and license, mount an external QC workbook when needed, select GPU access, and invoke one container.

The first primary image is `caibility1/smri_pipeline_win:runtime-v2-2026-07-22`. The image can be overridden with `SMRI_RUNTIME_IMAGE`.

## Mounts

- Batch directory: read-write at `/data`.
- FreeSurfer license: read-only at `/licenses/freesurfer/license.txt`.
- External QC workbook: read-only at `/inputs/qc/<filename>`.
- Pipeline source is not mounted at runtime.

All reports, manifests, logs, checkpoints, and imaging outputs remain under the host batch directory.

## Host Dependencies

Required: Windows WSL2 system capability, Docker Desktop Linux engine, and optional NVIDIA driver for GPU stages. Git is required only for source-based launchers and development. Host conda and a separate Ubuntu distribution are not required.

## Release Policy

Public tags use readable names: `runtime-v2-2026-07-22` and `latest`. Candidate tags remain local. Each image records source commit, release, model hashes, and tool versions.

## Acceptance Criteria

- The launchers run without `environment/windows_env.local.ps1` or host Python.
- No runtime step starts nested Docker or WSL.
- Container doctor verifies Python imports, models, FSL, ANTs, FreeSurfer, Workbench, and templates.
- Existing unit tests pass and new native-runtime tests pass.
- One preprocessing and one postprocessing path can run with host conda hidden.
- The old hybrid image and Git tag remain usable until the new release passes end-to-end validation.
