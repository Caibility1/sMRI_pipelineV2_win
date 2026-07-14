# sMRI preprocessing report: 0630_TEST

- Batch dir: `/public_bme2/bme-zhanghan/linmo2025/2026/0630_TEST`
- Generated: 2026-07-06T16:38:33

## Submitted jobs

- File: `submitted_jobs.csv`
- reg_job_id=, nnunet_job_id=, mask_all_job_id=, t1t2_acpc_job_id=3895189, justt1_acpc_job_id=3895191, t1t2_qc_job_id=3895190, justt1_qc_job_id=3895192, denoise_job_id=3895206

## 00 Age suffix

- File: `00_age_summary.csv`
- Rows: 10
- Status counts: renamed=10

## 01 T1/T2 standardization

- File: `01_copy_rename_summary.csv`
- Rows: 10
- Status counts: success=9, t1_only=1

## 02 T2-to-T1 input

- File: `02_t2tot1_input_summary.csv`
- Rows: 10
- Status counts: pending=9, t1_only=1

## 03 T2-to-T1 output

- File: `03_t2tot1_output_summary.csv`
- Rows: 10
- Status counts: success=9, t1_only=1

## 04 nnU-Net input

- File: `04_nnunet_input_summary.csv`
- Rows: 10
- Status counts: copied=10

## 05 nnU-Net output

- File: `05_nnunet_output_summary.csv`
- Rows: 10
- Status counts: success=10

## 06 mask_all

- File: `06_mask_all_summary.csv`
- Rows: 10
- Status counts: success=10

## 10 Split for ACPC

- File: `10_split_for_acpc_summary.csv`
- Rows: 10
- Status counts: copied=10
- Branch counts: T1T2=9, justT1=1

## 11 ACPC

- File: `11_acpc_summary.csv`
- Rows: 10
- Status counts: success=10
- Branch counts: T1T2=9, justT1=1

## 12 ACPC QC

- File: `12_acpc_qc_summary.csv`
- Rows: 10
- Status counts: success=10
- Branch counts: T1T2=9, justT1=1

## 20 Questionable/Fail denoise selection

- File: `20_questionable_summary.csv`
- Rows: 10
- Status counts: pass_not_selected=9, selected_for_denoise=1
- Branch counts: T1T2=9, justT1=1

## 21 Denoise submission

- File: `21_denoise_summary.csv`
- Rows: 1
- Status counts: success=1

## Denoise job tracking

- Job id: `3895260`
