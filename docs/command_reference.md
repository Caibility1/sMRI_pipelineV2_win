# Command Reference

普通用户只需要两个入口。镜像内部会设置 Python、FSL、ANTs、Workbench、FreeSurfer、nnU-Net 和 MoAR-Diff 环境变量，不需要手动 source。

## Preprocessing

```powershell
.\bin\smri_preprocessing.cmd <BATCH_DIR> [options]
```

常用参数：

- `--submit`：执行完整重任务；不加时只做准备和报告。
- `--stage1-only`：只到 registration、nnU-Net 和 mask。
- `--acpc-start`：从 ACPC 阶段续跑。
- `--denoising-start`：重新选择 questionable/fail 后运行去噪。
- `--denoising`：直接使用已有 `5_questionable\input` 运行去噪。
- `--no-denoise-submit`：生成去噪候选但不启动 MoAR-Diff。
- `--qc-excel <xlsx>`：QC/年龄表绝对路径，入口会自动挂载。
- `--age-source auto|excel|folder`：年龄来源。
- `--qc-mode visual|all-pass`：有配套图像 QC 用 `visual`；陌生数据无视觉 QC 用 `all-pass`。
- `--nnunet-task-name 523`：默认 Task523。
- `--acpc-jobs N`：ACPC 并发受试者数，默认 4；内存有限时降低。

`--registration-backend` 等 backend 参数为旧混合架构兼容选项。单镜像正常运行不要设置，runtime 会默认在当前容器执行。

## Presurf And Recon

```powershell
.\bin\smri_presurf_recon.cmd <BATCH_DIR> --submit --recon-jobs 1
```

- `--submit`：运行 presurf 和 FreeSurfer recon。
- `--presurf-only`：只生成 `7_presurf`，不启动 recon。
- `--recon-jobs N`：同时重建 N 名受试者。建议从 1 开始。
- `--Qsubmit`：已禁用；去噪结果必须先得到有效 `6_seg`。

`--presurf-backend`、`--recon-backend`、`--docker-tools-image` 是旧架构兼容参数，普通用户不需要。

## Runtime Image Override

测试新镜像时仅在当前 PowerShell 设置：

```powershell
$env:SMRI_RUNTIME_IMAGE = "smri_pipeline_win:runtime-test"
```

恢复发布版：

```powershell
Remove-Item Env:SMRI_RUNTIME_IMAGE
```

## Output

每步输出：

```text
>>> START <step> [<backend>]
    log: <path>
<<< COMPLETE <step> [<backend>] rc=0 elapsed=<time>
```

失败时查看打印的日志路径，以及：

```text
<BATCH_DIR>\manifests\windows_status.csv
<BATCH_DIR>\logs\preprocessing_report.md
<BATCH_DIR>\logs\postprocessing_report.md
```
