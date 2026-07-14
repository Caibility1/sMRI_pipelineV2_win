import os
import nibabel as nib
import numpy as np
from skimage.measure import label

# 指定路径
base_path = r'D:/Software/nnUNet_uii/sMRI_new_pipeline/data/0624_CBCP/2_T1_nnunet_output_530'

# 遍历 base_path 下的所有文件
for file_name in os.listdir(base_path):
    file_path = os.path.join(base_path, file_name)

    # 检查是否是文件且以 .nii.gz 结尾
    if os.path.isfile(file_path) and file_name.endswith(".nii.gz"):
        # 读取 .nii.gz 文件
        img = nib.load(file_path)
        data = img.get_fdata()

        # 标记连通区域
        labeled_data = label(data)

        # 计算连通区域的数量
        num_components = np.max(labeled_data)

        # 如果连通区域的数量大于1，则打印文件名
        if num_components > 1:
            print(f"File with more than one connected component: {file_name}")