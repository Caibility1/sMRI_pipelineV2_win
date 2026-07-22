# Teaching Demo Slim Runtime Design

## Goal

Replace the teaching image's full Windows pipeline base with the official FreeSurfer 8.1 image plus only the tools required for DICOM conversion, standard recon-all, and STL export.

## Compatibility

The current full demo is fixed by Git tag `demo-full-backup-2026-07-22` and Docker tag `2026-07-21`. DICOM inventory, explicit series selection, recon checkpoints, subject filtering, T2 pial policy, and STL outputs remain compatible.

## Image Contents

The slim image contains FreeSurfer 8.1, dcm2niix, Python 3 standard library, and the demo source at `/opt/smri/pipeline_demo`.

It does not contain FSL, ANTs, Workbench, nnU-Net, MoAR-Diff, PyTorch/CUDA, infant templates, or the full pipeline conda environments.

## Active Workflow

`DICOM -> dcm2niix inventory -> visual series choice -> standardized T1/T2 -> standard recon-all -> pial STL`.

Independent FSL T2-to-T1 registration is removed from the active slim workflow. FreeSurfer can still use a suitable 3D T2 through `-T2` and `-T2pial`. Legacy registration scripts remain in source history and are not deleted.

## Interface

The existing container commands remain: `reconstruct`, `stl`, `doctor`, and `help`. Existing PS1 launchers remain optional host conveniences.

The first public image is `caibility1/smri_pipeline_demo:slim-v2-2026-07-22`; `latest` is updated only after one complete reconstruction and STL export.

## Acceptance Criteria

- Dockerfile no longer references the full Windows image.
- Doctor does not require FSL.
- All existing non-registration unit tests pass; registration tests are replaced with assertions that the active controller does not expose registration.
- DICOM inventory and selection output remain unchanged.
- One subject completes recon-all and creates left, right, and combined pial STL files.
- Compressed registry size is measured and documented.
