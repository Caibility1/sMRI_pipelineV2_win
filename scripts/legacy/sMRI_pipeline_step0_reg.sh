#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J sMRI_pipeline_step0
#SBATCH -N 1
#SBATCH -n 5
#SBATCH -t 1-00:00:00
#SBATCH -o reg.out

# 加载必要模块
module load compiler/gcc/7.3.1
module load tools/parallel/20200122
module load apps/fsl/6.0

export FSLOUTPUTTYPE=NIFTI_GZ
source ${FSLDIR}/etc/fslconf/fsl.sh

# === 设置脚本路径和数据路径 ===
# 你的原始数据目录（每个被试一个文件夹）
BASE_DIR=/public_bme2/bme-zhanghan/linmo2025/2026/0310_CBCP/1_T2toT1/data

# QC输出图片保存目录
QC_IMAGE_DIR=/public_bme2/bme-zhanghan/linmo2025/2026/0310_CBCP/1_T2toT1/result

# 并行调用（每个被试为一个任务）
#ls $BASE_DIR | parallel -j 20 /public_bme2/bme-zhanghan/linmo2025/0_code/reg.sh $BASE_DIR/{} $QC_IMAGE_DIR

bash /public_bme2/bme-zhanghan/linmo2025/0_code/reg.sh $BASE_DIR $QC_IMAGE_DIR