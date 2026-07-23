# Codespaces Prebuild Runtime Design

## Goal

Provide a browser-only Linux teaching environment that can run one real
FreeSurfer reconstruction without Docker Desktop, WSL2, Conda, or host-side
neuroimaging tools.

## Architecture

The `demo` branch remains the source of truth. A dedicated image,
`caibility1/smri_pipeline_demo:cloud-nomcr-v1-2026-07-23`, contains Rocky
Linux, FreeSurfer 8.1, dcm2niix, Python, and a snapshot of the repository.
MATLAB Runtime is deliberately excluded because the teaching workflow only
uses standard `recon-all`, T2-pial, and `mris_convert`.

Codespaces starts this image directly as its devcontainer. There is no nested
Docker daemon. GitHub Codespaces Prebuild prepares the branch and image before
students create a Codespace, avoiding the image-pull timeout seen during direct
creation.

The checked-out repository is the active code at runtime. The image snapshot is
a fallback and supplies the runtime files needed before the workspace mount is
ready. Linux launchers in `bin/` continue to delegate to the existing scripts
under `scripts/jobs/`; reconstruction algorithms are unchanged.

## Image Construction

The image is flattened from the official `freesurfer/freesurfer:8.1.0` image
with a BuildKit bind mount. `/usr/local/freesurfer/8.1.0-1/MCRv97` is excluded
while all other FreeSurfer files are copied into a fresh Rocky Linux 8 final
stage. This removes the MCR bytes from the final layer instead of hiding them
under a later deletion layer.

The image retains:

- standard FreeSurfer binaries, models, average data, Python runtime, and
  `fsaverage`;
- dcm2niix copied from the existing portable tools image;
- the Demo repository and Linux entrypoints.

## Resource Policy

- A 4-core, 16 GB Codespace is accepted for the one-subject reliability test,
  with `--recon-jobs 1 --recon-threads 4`.
- 8 cores and 32 GB RAM remain the recommended classroom reconstruction size
  when GitHub offers that machine type.
- 64 GB RAM is not assumed to be freely or consistently available.
- The cloud workspace must contain only de-identified teaching data.

## Validation

1. Repository tests assert the no-MCR image contract and devcontainer tag.
2. A local image smoke test checks `python3`, `dcm2niix`, `recon-all`, and
   `mris_convert`.
3. A Codespaces Prebuild is configured for the `demo` branch.
4. A new Codespace created from that prebuild runs one de-identified subject
   through reconstruction and STL export.
5. The existing local multi-subject reconstruction container is monitored but
   never stopped by this work.

## Fallback

If GitHub cannot create or retain the prebuild because of account quota or the
32 GB storage ceiling, the supported fallback is the existing local Docker
workflow. Docker-outside-of-Docker is not the primary design because it adds a
second runtime layer and still requires pulling the large image after startup.

## Execution Note

The no-MCR candidate was built and validated locally at 10.77 GB, but its new
11.38 GB registry layer could not be published over the current 0.17 MB/s
uplink. The first real Codespaces validation therefore uses the already
published `caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23` image with
Prebuild. The no-MCR Dockerfile remains the next release candidate and is not
presented as a published image.