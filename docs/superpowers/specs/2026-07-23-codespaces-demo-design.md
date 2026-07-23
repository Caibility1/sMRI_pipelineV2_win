# Codespaces Teaching Demo Design

## Goal

Run the existing teaching Demo from a browser-based GitHub Codespace without
installing Docker Desktop, WSL2, Conda, FSL, or FreeSurfer on the student's PC.

## Selected Architecture

GitHub continues to host the `demo` branch and Docker Hub continues to host
`caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23`. A committed
`.devcontainer/devcontainer.json` asks Codespaces to start that exact image on
an amd64 Linux VM selected from the machine types available to the user.

The repository remains mounted as the editable workspace. New Linux launchers
in `bin/` call the existing job scripts from the checked-out repository, so the
algorithm and checkpoint logic remain unchanged. PowerShell launchers continue
to serve Windows hosts.

## Student Data Flow

1. Create a Codespace from the `demo` branch.
2. Upload an anonymized DICOM folder and `license.txt` into ignored workspace
   directories.
3. Run `--dcm2niix-only`, inspect all NIfTI candidates, and select a T1/T2.
4. Run standard `recon-all`, then export pial STL files.
5. Download results and delete the Codespace after class.

No identifiable DICOM may be uploaded to a public cloud. The first remote
validation is limited to `doctor` and command help until anonymization is
confirmed.

## Storage And Compute

- Recommended full-reconstruction host: 8 CPUs and 32 GB RAM; smaller machines are smoke-test only.
- GitHub Free includes 120 core-hours and 15 GB-month storage. One 8-core
  Codespace therefore has about 15 wall-clock hours before exhausting the
  monthly compute allowance.
- A student PC stores only the source upload and downloaded output. The
  14.4 GB runtime image remains in the cloud.
- Data and results are ignored by Git and the Codespace should be deleted after
  results are downloaded.

## Error Handling

- The post-create script reports missing required tools but never downloads or
  mutates the runtime.
- Linux launchers reject missing arguments through the existing job scripts.
- The doctor command fails when the FreeSurfer license has not been uploaded.
- Reconstruction stays synchronous so the terminal and logs show real status.

## Validation

1. Unit tests check the devcontainer image, host requirements, ignored data
   paths, and Linux launcher delegation.
2. A local container test mounts the current repository into the published
   image and runs the same Linux launchers used by Codespaces.
3. A real Codespace smoke test runs `doctor` and both launchers with `--help`.
4. Real MRI upload and reconstruction require confirmed anonymized input.
