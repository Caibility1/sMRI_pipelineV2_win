# sMRI 教学 Demo 学生操作手册

所有命令都在 **Windows PowerShell** 中运行。Docker Desktop 只需保持 `Engine running`，不需要在镜像页面点 `Run`。

## 1. 课前必须完成

1. Windows 10/11 64 位，BIOS/UEFI 虚拟化已开启。
2. WSL2 系统能力已启用。
3. Docker Desktop 已安装并成功启动。
4. 代码文件夹、Demo 镜像和 `license.txt` 已准备好。
5. Docker 与数据盘合计至少保留 80 GB，建议 100 GB；一次只运行一个重建任务。

主机不需要安装 Conda、Ubuntu、FSL、ANTs 或 FreeSurfer。

## 2. 在线获取

```powershell
git clone --branch demo https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipeline_demo
cd D:\sMRI_pipeline_demo
docker pull caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24
```

## 3. 离线获取

从教师提供的离线包解压代码，然后导入镜像：

```powershell
docker load -i E:\smri_offline\caibility1_smri_pipeline_demo_slim-v2.3-2026-07-24.tar
cd D:\sMRI_pipeline_demo
```

离线包应同时包含代码 ZIP、镜像 TAR、`license.txt` 和 `SHA256SUMS.txt`。课堂当天不依赖 GitHub、Docker Hub 或 VPN。

## 4. 第一次检查

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
.\docker\doctor_demo.ps1 -LicensePath $env:SMRI_FS_LICENSE
```

看到 `python3`、`dcm2niix`、`recon-all`、`mris_convert` 和 license 均为 `[OK]` 后再处理数据。

## 5. 数据目录

```text
D:\MRI_CLASS\
  26_MRIdata\
    001\
      ... DICOM files ...
    003\
      ... DICOM files ...
```

每名受试者一个文件夹。文件夹名就是 ID，`001` 的前导零会保留。不要把不同人的 DICOM 混在一起。

## 6. 第一条命令：全部 DICOM 转 NIfTI

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --raw-dir 26_MRIdata `
  --dcm2niix-only
```

这一步只转换，不开始 FreeSurfer。检查：

```text
D:\MRI_CLASS\1_T2toT1\dicom_candidates\<ID>\*.nii.gz
D:\MRI_CLASS\manifests\00_dicom_series_inventory.csv
```

用 ITK-SNAP 同时查看轴位、冠状位和矢状位。优先选择结构完整、边界清楚、无明显运动重影的三维 T1。scout、motion curve 和明显失败序列不进入后续流程。

## 7. 多个 T1 时明确选择

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --raw-dir 26_MRIdata `
  --select-only `
  --subject 001 `
  --t1-series 302 `
  --force-convert
```

把 `001` 和 `302` 换成 inventory 中的真实 ID 与 `series_number`。有合适 T2 时可增加 `--t2-series 401`；没有 T2 就使用 T1-only。

确认标准输入存在：

```text
D:\MRI_CLASS\1_T2toT1\data\<ID>\T1.nii.gz
```

## 8. 第二条命令：开始标准重建

先跑一名受试者：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --skip-dicom `
  --subject 001 `
  --recon-jobs 1 `
  --recon-threads 4
```

这是同步运行，PowerShell 窗口会持续显示进度。重复同一命令会检查已有结果并断点续跑。不要删除 `3_recon` 中的部分结果。

## 9. 导出 STL

```powershell
.\bin\smri_3d_print.ps1 D:\MRI_CLASS --subject 001
```

结果：

```text
D:\MRI_CLASS\4_stl\001\lh.pial.stl
D:\MRI_CLASS\4_stl\001\rh.pial.stl
D:\MRI_CLASS\4_stl\001\brain.pial.stl
```

`brain.pial.stl` 是完整皮层表面。切片软件中的“一层预览”只是打印路径的一层，不等于一个独立脑解剖切面。薄片打印需要另外生成有厚度的切面 STL。

## 10. 查看日志

```text
D:\MRI_CLASS\logs\recon\<ID>.log
D:\MRI_CLASS\logs\stl\<ID>.log
D:\MRI_CLASS\manifests\30_recon_summary.csv
D:\MRI_CLASS\manifests\40_stl_summary.csv
```

长时间没有新输出时先看日志是否继续增长，再看 Docker Desktop 是否仍为 `Engine running`。不要因为任务运行很久就直接删除容器或数据目录。
