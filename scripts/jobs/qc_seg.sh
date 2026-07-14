#!/bin/bash
#SBATCH -J qc_seg
#SBATCH -p bme_cpu
#SBATCH --mem=20G
#SBATCH --cpus-per-task=1
#SBATCH -N 1
#SBATCH -t 6-24:00:00
#SBATCH -o qc_seg.out 
#SBATCH -e qc_seg.err 

hostname
date
source ~/.bash_profile

# 设置基础路径
SOURCE_DIR="/public_bme2/bme-zhanghan/fyx/sMRI_new_pipeline/0722_CBCP/seg/data"
QC_DIR="/public_bme2/bme-zhanghan/fyx/sMRI_new_pipeline/0722_CBCP/seg/qc"

# 确保QC目录存在
mkdir -p "${QC_DIR}/tissue"
mkdir -p "${QC_DIR}/dkstruct"

# 创建Python脚本来处理可视化
cat > visualize_three_view.py << 'EOF'
import sys
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

def create_three_view(input_file, output_file, file_type=""):
    # 加载图像
    img = nib.load(input_file)
    data = img.get_fdata()

    # 创建自定义颜色映射
    if file_type == "tissue":
        # 固定颜色：黑/红/绿/蓝
        colors = ['black', 'red', 'green', 'blue']
        cmap = ListedColormap(colors)
        vmax = 3
    elif file_type == "dkstruct":
        # 自动生成离散色图（支持多标签）
        labels = np.unique(data)
        labels = labels[labels != 0]
        cmap = plt.colormaps.get_cmap('tab20').resampled(len(labels))
        vmax = len(labels)
    else:
        raise ValueError("file_type must be 'tissue' or 'dkstruct'")
    
    # 创建图像布局 (1行3列)
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f'{file_type.capitalize()} - Three Views', fontsize=16)
    
    # 获取中心切片
    x_center = data.shape[0] // 2
    y_center = data.shape[1] // 2
    z_center = data.shape[2] // 2
    
    # 冠状面 (Coronal)
    ax1.imshow(np.rot90(data[x_center, :, :]), cmap=cmap, vmin=0, vmax=vmax)
    ax1.set_title('Coronal View')
    ax1.axis('off')
    
    # 矢状面 (Sagittal)
    ax2.imshow(np.rot90(data[:, y_center, :]), cmap=cmap, vmin=0, vmax=vmax)
    ax2.set_title('Sagittal View')
    ax2.axis('off')
    
    # 横断面 (Axial)
    ax3.imshow(np.rot90(data[:, :, z_center]), cmap=cmap, vmin=0, vmax=vmax)
    ax3.set_title('Axial View')
    ax3.axis('off')
    
    # 调整布局
    plt.tight_layout()
    
    # 保存结果
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python script.py input_file output_file title_suffix")
        sys.exit(1)
    create_three_view(sys.argv[1], sys.argv[2], sys.argv[3])
EOF

# 遍历源目录中的所有被试文件夹
for subject_dir in ${SOURCE_DIR}/*; do
    if [ -d "$subject_dir" ]; then
        # 提取被试ID（文件夹名）
        subject_name=$(basename "$subject_dir")
        echo "Processing subject: ${subject_name}"

        # 找到tissue文件
        tissue_file="${subject_dir}/tissue.nii.gz"
        if [ -f "$tissue_file" ]; then
            # 设置输出文件名
            output_tissue="${QC_DIR}/tissue/${subject_name}_tissue_3view.png"
            
            # 运行Python脚本生成可视化
            python visualize_three_view.py "$tissue_file" "$output_tissue" "tissue"
            echo "Created three view visualization for ${subject_name}"
        else
            echo "Warning: Could not find tissue file for ${subject_name}"
        fi

        dkstruct_file="${subject_dir}/dk-struct.nii.gz"
        if [ -f "$dkstruct_file" ]; then
            output_dkstruct="${QC_DIR}/dkstruct/${subject_name}_dkstruct_3view.png"
            python visualize_three_view.py "$dkstruct_file" "$output_dkstruct" "dkstruct"
            echo "Created dk-struct visualization for ${subject_name}"
        else
        echo "Warning: Could not find DK Structfile for ${subject_name}"
        fi
    fi
done

echo "All processing completed!"
date


