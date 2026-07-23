# GitHub Codespaces Student Tutorial

This path runs the teaching Demo on a temporary Linux computer hosted by
GitHub. The student PC needs a browser and a GitHub account. It does not need
Docker Desktop, WSL2, Conda, FSL, ANTs, or FreeSurfer.

## Privacy Gate

Only upload de-identified DICOM. Before cloud upload, remove patient name,
birth date, hospital number, accession number, and other identifying fields.
Do not upload an identifiable clinical scan to Codespaces.

## 1. Start The Cloud Computer

Open:

```text
https://codespaces.new/Caibility1/sMRI_pipelineV2_win/tree/demo
```

Choose `New with options` and confirm:

- Branch: `demo`
- Dev container: `sMRI teaching demo`
- Machine: choose the largest machine that GitHub offers to your account

For a complete FreeSurfer reconstruction, 8 cores and 32 GB RAM are recommended
when GitHub offers that machine. The project reliability test uses the available
4-core, 16 GB machine with one subject and four threads; it is slower and has
less memory margin, so do not run subjects concurrently on that size.

Click `Create codespace`. The `demo` branch uses a Codespaces Prebuild based on
`caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23`. When the prebuild is
ready, GitHub starts the prepared Linux runtime instead of making every student
download and unpack FreeSurfer during creation. The student's local disk does
not store the image.


If GitHub opens a recovery container or reports that the image could not be
pulled, delete that Codespace and wait for the maintainer to confirm that the
`demo` prebuild is green before trying again.

## 2. Upload The License And Data

In the browser VS Code Explorer:

1. Upload the teacher-provided `license.txt` as `.secrets/license.txt`.
2. Put the anonymized data under `cloud_data/MRI_CLASS/0_rawdata/<ID>/`.

Example:

```text
cloud_data/
  MRI_CLASS/
    0_rawdata/
      001/
        ... DICOM files ...
```

Run the health check in the Codespaces terminal:

```bash
bash docker/demo_entrypoint.sh doctor
```

Continue only when `python3`, `dcm2niix`, `recon-all`, `mris_convert`, and
`FS_LICENSE` are all `[OK]`.

## 3. Convert Every DICOM Series

```bash
./bin/smri_reconstruction.sh "$PWD/cloud_data/MRI_CLASS" --submit --dcm2niix-only
```

Review:

```text
cloud_data/MRI_CLASS/1_T2toT1/dicom_candidates/<ID>/
cloud_data/MRI_CLASS/manifests/00_dicom_series_inventory.csv
```

Download uncertain NIfTI candidates for ITK-SNAP review when the browser
preview is insufficient.

## 4. Select T1 And Optional T2

For an unambiguous subject:

```bash
./bin/smri_reconstruction.sh "$PWD/cloud_data/MRI_CLASS" --submit --select-only --subject 001
```

When several T1 candidates remain:

```bash
./bin/smri_reconstruction.sh "$PWD/cloud_data/MRI_CLASS" --submit --select-only \
  --subject 001 --t1-series 302 --t2-series 401 --force-convert
```

Omit `--t2-series` for T1-only reconstruction.

## 5. Run Standard FreeSurfer Reconstruction

Run one subject at a time:

```bash
./bin/smri_reconstruction.sh "$PWD/cloud_data/MRI_CLASS" --submit --skip-dicom \
  --subject 001 --recon-jobs 1 --recon-threads 4
```

The command is synchronous. Keep the Codespace running until the terminal says
`reconstruction pipeline complete`. Repeating the command resumes from
existing FreeSurfer checkpoints. On an 8-core, 32 GB Codespace, change only
`--recon-threads 4` to `--recon-threads 8`.

## 6. Export STL

```bash
./bin/smri_3d_print.sh "$PWD/cloud_data/MRI_CLASS" --subject 001
```

The combined printable surface is:

```text
cloud_data/MRI_CLASS/4_stl/001/brain.pial.stl
```

## 7. Download And Delete

Download the required STL, manifests, and logs. Then visit:

```text
https://github.com/codespaces
```

Stop and delete the Codespace after confirming the download. GitHub Free
provides 120 core-hours and 15 GB-month of Codespaces storage. An 8-core
machine consumes eight core-hours per wall-clock hour, so one free account has
about 15 wall-clock hours per month at this size.
