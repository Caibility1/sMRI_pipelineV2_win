#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J sMRI_pipeline_step1
#SBATCH -N 1
#SBATCH -n 20
#SBATCH -t 1-00:00:00
#SBATCH -o preprocess.out

module load compiler/gcc/7.3.1
module load tools/parallel/20200122
module load apps/fsl/6.0
module load apps/ants
export FREESURFER_HOME=/public/software/apps/freesurfer_infant/freesurfer/
source $FREESURFER_HOME/SetUpFreeSurfer.sh
# source /hpc/data/home/bme/yubw/anaconda3/bin/activate ddpm

## 导入workbench
export PATH=$PATH:"/public_bme/home/zhanghan_group_public/software/workbench-linux64-v2.0.0/workbench/bin_linux64"

## 处理数据路径(需修改)
T1_T2_pass_dir=/public_bme2/bme-zhanghan/linmo2025/2026/0416_XUXIU/justT1
#T1_T2_pass_dir=/public_bme2/bme-zhanghan/linmo2025/2026/0512_questionable/T1T2

## Template路径
template_dir=/public_bme/data/zhanghan_group/sMRI_pipeline_new/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0/

ls $T1_T2_pass_dir | parallel -j 20 /public_bme/data/zhanghan_group/sMRI_pipeline_new/preprocessing_ttl_v1.sh $T1_T2_pass_dir/{} $template_dir
