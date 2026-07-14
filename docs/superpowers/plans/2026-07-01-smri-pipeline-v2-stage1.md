# sMRI Pipeline V2 Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first reusable command-line/Slurm layer for preprocessing from `1_T2toT1/data` through `3_skullstrip/data`, while leaving ACPC and recon work for the next staged pass.

**Architecture:** Keep legacy algorithm scripts intact where possible and add numbered V2 Python tools only. Shell entrypoints and job wrappers are not numbered. The bin layer has only two long-term entries: `smri_preprocessing.sh` for intake through ACPC and `smri_presurf_recon.sh` for post-segmentation processing. This pass implements the currently safe subset of `smri_preprocessing.sh` up to mask-all.

**Tech Stack:** Bash, Slurm `sbatch` dependencies, Python 3 standard library, pandas/openpyxl for QC Excel, nibabel/numpy for NIfTI masking, nnU-Net v1 CLI `nnUNet_predict`.

---

### Task 1: Numbered Stage 1 Python Tools

**Files:**
- Create: `scripts/steps/1_standardize_t1_t2_v2.py`
- Create: `scripts/steps/2_add_age_suffix_v2.py`
- Create: `scripts/steps/3_prepare_nnunet_input_v2.py`
- Create: `scripts/steps/4_check_t2tot1_outputs_v2.py`
- Create: `scripts/steps/5_check_nnunet_outputs_v2.py`
- Create: `scripts/steps/6_mask_all_v2.py`
- Test: `tests/test_stage1_v2.py`

- [ ] Write failing unit tests for trailing age parsing, T1/T2 candidate detection, nnUNet case IDs, dataset JSON, and mask-all shape checks.
- [ ] Implement the Python scripts with `--batch-dir`, CSV summaries, conservative overwrite handling, and nonzero exit for strict intake failures.
- [ ] Run `python -m unittest discover -s tests -v` and keep it green.

### Task 2: Slurm Job Wrappers

**Files:**
- Create: `scripts/jobs/sMRI_pipeline_step0_reg2_v2.sh`
- Create: `scripts/jobs/nnunet_task523.sh`
- Create: `scripts/jobs/mask_all.sh`

- [ ] Implement `.sh` Slurm scripts only, no `.slurm` files and no numbered shell names.
- [ ] Keep `reg2.sh` as the registration algorithm worker.
- [ ] Print environment diagnostics in each job.
- [ ] Use batch-local input/output paths and write logs under `<BATCH_DIR>/logs` and `<BATCH_DIR>/1_T2toT1/logs` or `<BATCH_DIR>/2_nnunet_output/logs`.

### Task 3: Two-Part Bin Interface

**Files:**
- Create: `bin/smri_preprocessing.sh`
- Create: `bin/smri_presurf_recon.sh`

- [ ] Implement `smri_preprocessing.sh <BATCH_DIR> [--to maskall]` for the current completed stage.
- [ ] Submit registration and nnUNet jobs in parallel, then submit mask-all with `--dependency=afterany:<reg_jid>:<nnunet_jid>`.
- [ ] Add `2_smri_presurf_recon.sh` as a real entrypoint that validates arguments and explains that implementation starts after Stage 1/ACPC, without touching data.

### Task 4: Environment Notes

**Files:**
- Create: `environment/environment.yml`
- Create: `environment/env_notes.md`

- [ ] Name the conda environment `sMRI_pipeline`.
- [ ] Document nnU-Net v1 variables: `nnUNet_raw_data_base`, `nnUNet_preprocessed`, `RESULTS_FOLDER`.
- [ ] Document the current docx-derived predict command shape: `nnUNet_predict -i ... -o ... -m 3d_fullres -t 523`.

### Self-Review

- Scope is Stage 1 implementation plus bin naming correction requested by the user.
- ACPC, questionable denoise, presurf, recon, NAS automation, and container builds are intentionally not implemented in this pass.
- No password-bearing commands from the old docx are copied into new scripts.
