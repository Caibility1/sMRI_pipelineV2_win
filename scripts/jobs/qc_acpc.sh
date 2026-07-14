#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -J qc_acpc
#SBATCH -N 1
#SBATCH -n 5
#SBATCH -t 1-00:00:00
#SBATCH -o qc_acpc.out 
#SBATCH -e qc_acpc.err 

module load compiler/gcc/7.3.1
module load tools/parallel/20200122
module load apps/fsl/6.0

# 设置基础路径
#SOURCE_DIR=${1:-/public_bme2/bme-zhanghan/fyx/sMRI_new_pipeline/0624_CBCP/preprocessing/data}
#SOURCE_DIR=${1:-/public_bme2/bme-zhanghan/linmo2025/2026/0409_XUXIU/6_result/results}

SOURCE_DIR=${1:-/public_bme2/bme-zhanghan/linmo2025/2026/0511_questionable/T1T2}

#QC_DIR=${2:-/public_bme2/bme-zhanghan/fyx/sMRI_new_pipeline/0624_CBCP/preprocessing/qc}
#QC_DIR=${2:-/public_bme2/bme-zhanghan/linmo2025/2026/0409_XUXIU/6_result/qc}
QC_DIR=${2:-/public_bme2/bme-zhanghan/linmo2025/2026/0512_questionable/T1T2/qc}

# 确保QC目录存在
mkdir -p ${QC_DIR}

# 遍历源目录中的所有被试文件夹
for subject_dir in "$SOURCE_DIR"/*; do
   if [ -d "$subject_dir" ]; then
       # 提取被试ID
       subject_name=$(basename "$subject_dir")
       
       # 检查是否包含mo后缀
       if [[ "$subject_name" =~ "mo" ]]; then
           # 如果包含mo后缀,则去除
           new_subject_name=$(echo "$subject_name" | sed 's/_[0-9]*mo$//')
           echo "Processing subject (removing mo suffix): $subject_name -> $new_subject_name"
       else
           # 如果不包含mo后缀,则保持原名
           new_subject_name="$subject_name"
           echo "Processing subject (no mo suffix): $subject_name"
       fi
       
       # 检查T1_acpc.nii.gz文件是否存在
       if [ -f "${subject_dir}/T1_acpc.nii.gz" ]; then
           # 使用FSL slicer生成中缝矢状面图像
           slicer "${subject_dir}/T1_acpc.nii.gz" -x 0.5 "${QC_DIR}/${new_subject_name}.png"
           echo "Created QC image for ${new_subject_name}"
       else
           echo "Warning: T1_acpc.nii.gz not found for ${new_subject_name}"
       fi
   fi
done

echo "Processing completed!"