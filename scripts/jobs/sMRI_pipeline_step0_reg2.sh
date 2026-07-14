#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J sMRI_pipeline_step0_reg2
#SBATCH -N 1
#SBATCH -c 5
#SBATCH -t 2-00:00:00
#SBATCH -o reg2.out

module load compiler/gcc/7.3.1
module load tools/parallel/20200122
module load apps/fsl/6.0

export FSLOUTPUTTYPE=NIFTI_GZ
source ${FSLDIR}/etc/fslconf/fsl.sh

# === 设置脚本路径和数据路径 ===
BASE_DIR=/public_bme2/bme-zhanghan/linmo2025/2026/0622_CBCP/0_rawdata
QC_IMAGE_DIR=/public_bme2/bme-zhanghan/linmo2025/2026/0622_CBCP/1_T2toT1/qc
SCRIPT=/public_bme2/bme-zhanghan/linmo2025/0_code/reg2.sh

mkdir -p "$QC_IMAGE_DIR"

# 并行调用：每个被试目录作为一个任务
find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d | \
parallel -j ${SLURM_CPUS_PER_TASK:-5} bash "$SCRIPT" {} "$QC_IMAGE_DIR"