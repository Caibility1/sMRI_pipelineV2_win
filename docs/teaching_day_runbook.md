# 教学日前验证与当天运行清单

## 教学日前

1. 在与课堂电脑相近的机器上完成镜像 pull 和 `doctor_demo.ps1`。
2. 将全部真实 DICOM 按受试者 ID 放入 `0_rawdata`。
3. 用 `--dcm2niix-only` 转换全部序列，核对两个 manifest 并完成视觉 QC。
4. 用 `--select-only` 标准化确认的 T1 和可选 T2。
5. 用 `--skip-dicom --recon-jobs 1` 完成所有受试者标准重建。
6. 确认 `30_recon_summary.csv` 中每名受试者均为 `success`。
7. 运行 `smri_3d_print.ps1`，确认 `40_stl_summary.csv` 全部成功。
8. 在实际使用的切片软件中打开每个 `brain.pial.stl`，确认尺寸、网格和打印方向。
9. 将完整批次做只读备份，尤其保存 `3_recon`、`4_stl`、`logs` 和 `manifests`。

## 课堂当天

1. 先启动 Docker Desktop，等待 Engine running。
2. 运行 `docker version`，确认 Client/Server 都可见。
3. 学生把自己的 DICOM 放入各自 `<BATCH_DIR>\0_rawdata\<ID>`。
4. 学生亲自运行：

```powershell
.\bin\smri_reconstruction.ps1 <BATCH_DIR> --submit --dcm2niix-only
```

5. 展示序列 inventory、全部候选 NIfTI 和 DICOM 到 NIfTI 的概念，并完成视觉 QC。
6. 确认序列后，先标准化 T1/T2：

```powershell
.\bin\smri_reconstruction.ps1 <BATCH_DIR> --submit --select-only
```

7. 确认标准化文件后启动重建：

```powershell
.\bin\smri_reconstruction.ps1 <BATCH_DIR> --submit --skip-dicom --recon-jobs 1
```

8. 解释 recon 会继续较长时间；使用教学日前的成功结果讲解 brainmask、aseg 和 pial。
9. 使用提前导出的 STL 进入切片和 3D 打印环节。

## 不可省略的验收点

- `T1.nii.gz` 确实来自高分辨率 3D T1，而不是 scout 或 motion 序列。
- `scripts/recon-all.done`、左右 `pial`、`brainmask.mgz` 和 `aseg.mgz` 同时存在。
- STL 不是空文件，且已在切片软件中实际打开。
- 原始数据和提前完成结果均有备份。
