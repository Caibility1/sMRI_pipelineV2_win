#!/usr/bin/env python3
"""Prepare 7_presurf inputs from 6_seg segmentation outputs."""

import argparse
import csv
import os
import shutil
from pathlib import Path

import SimpleITK as sitk
import numpy as np

def get_masked_T1(T1_nii, skull_strip):
    T1 = sitk.GetArrayFromImage(T1_nii)
    masked = T1.copy()
    masked[skull_strip == 0] = 0
    masked_nii = sitk.GetImageFromArray(masked)
    masked_nii.SetDirection(T1_nii.GetDirection())
    masked_nii.SetOrigin(T1_nii.GetOrigin())
    masked_nii.SetSpacing(T1_nii.GetSpacing())
    return masked_nii


def get_aseg(T1_nii, tissue, dk):
    """
    根据输入的 tissue 和 dk-struct 图像，生成符合 FreeSurfer 8.1 标准的 aseg 分割图像。
    所有标签值均已根据官方 FreeSurferColorLUT 校对。
    """
    aseg = np.zeros_like(dk, dtype=np.uint16)
    gm_mask = (tissue == 2)

    # --- 1. 大脑主要组织 ---
    aseg[dk == 91] = 2
    aseg[dk == 92] = 41
    for i in range(1, 91, 2):
        aseg[(dk == i) & gm_mask] = 3
        aseg[(dk == (i + 1)) & gm_mask] = 42

    # --- 2. 小脑 ---
    aseg[dk == 95] = 7
    aseg[dk == 96] = 46
    aseg[dk == 93] = 8
    aseg[dk == 94] = 47

    # --- 3. 脑干 ---
    aseg[dk == 99] = 16

    # --- 4. 脑室 + 脉络丛 ---
    aseg[dk == 55] = 4
    aseg[dk == 57] = 5
    aseg[dk == 56] = 43
    aseg[dk == 58] = 44
    aseg[dk == 97] = 14
    aseg[dk == 98] = 15
    aseg[dk == 53] = 31
    aseg[dk == 54] = 63

    # --- 5. 皮层下结构 ---
    aseg[dk == 41] = 11
    aseg[dk == 42] = 50
    aseg[dk == 43] = 12
    aseg[dk == 44] = 51
    aseg[dk == 45] = 13
    aseg[dk == 46] = 52
    aseg[dk == 47] = 10
    aseg[dk == 48] = 49
    aseg[dk == 49] = 26
    aseg[dk == 50] = 58
    aseg[dk == 51] = 28
    aseg[dk == 52] = 60
    aseg[dk == 35] = 17
    aseg[dk == 36] = 53
    aseg[dk == 39] = 18
    aseg[dk == 40] = 54

    # --- 6. 胼胝体 ---
    aseg[dk == 106] = 251
    aseg[dk == 105] = 252
    aseg[dk == 104] = 253
    aseg[dk == 103] = 254
    aseg[dk == 102] = 255

    aseg_nii = sitk.GetImageFromArray(aseg)
    aseg_nii.SetDirection(T1_nii.GetDirection())
    aseg_nii.SetOrigin(T1_nii.GetOrigin())
    aseg_nii.SetSpacing(T1_nii.GetSpacing())
    return aseg_nii


# ==============================================================================
#                               主程序循环
# ==============================================================================

# 输入路径
source_dir = r"/public_bme2/bme-zhanghan/linmo2025/2026/0507_ASD/4_sMRI_segmentation/"
# 输出根路径
target_root = r"/public_bme2/bme-zhanghan/linmo2025/2026/0507_ASD/8_presurf/"

for dir_name in sorted(os.listdir(source_dir)):
    source_subdir = os.path.join(source_dir, dir_name)
    if not os.path.isdir(source_subdir):
        continue

    r'''
    # 解析目录名 N001_0302010001_1mo
    parts = dir_name.split("_")
    if len(parts) < 2:
        print(f"跳过: {dir_name} (目录名格式不对)")
        continue

    site_code = parts[1][:4]  # 取中间的 4 位 (0302)
    if site_code != "0302":
        print(f"跳过: {dir_name} (site_code={site_code})")
        continue
    r'''

    # 输出路径
    target_subdir = os.path.join(target_root, dir_name)
    os.makedirs(target_subdir, exist_ok=True)

    # 检查输入文件
    brain_path = os.path.join(source_subdir, 'brain.nii.gz')
    dk_path = os.path.join(source_subdir, 'dk-struct.nii.gz')
    tissue_path = os.path.join(source_subdir, 'tissue.nii.gz')

    if not (os.path.exists(brain_path) and os.path.exists(dk_path) and os.path.exists(tissue_path)):
        print(f"跳过: {dir_name} (缺少 brain/dk/tissue)")
        continue

    try:
        brain_nii = sitk.ReadImage(brain_path)
        dk_nii = sitk.ReadImage(dk_path)
        tissue_nii = sitk.ReadImage(tissue_path)

        if (brain_nii.GetSize() != dk_nii.GetSize()) or (brain_nii.GetSize() != tissue_nii.GetSize()):
            print(f"跳过: {dir_name} (尺寸不一致)")
            continue

        tissue = sitk.GetArrayFromImage(tissue_nii)
        dk = sitk.GetArrayFromImage(dk_nii)

        aseg_nii = get_aseg(brain_nii, tissue, dk)

        shutil.copy(brain_path, os.path.join(target_subdir, 'masked.nii.gz'))
        sitk.WriteImage(aseg_nii, os.path.join(target_subdir, 'aseg.nii.gz'))
        shutil.copy(brain_path, os.path.join(target_subdir, 'mprage.nii.gz'))

        print(f"已处理: {dir_name} -> {target_subdir}")

    except Exception as e:
        print(f"处理 {dir_name} 时出错: {e}")

print("\n所有文件夹处理完成!")
