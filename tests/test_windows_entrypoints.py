import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath


REPO = Path(__file__).resolve().parents[1]
STEPS = REPO / "scripts" / "steps"


def load_steps_module(name):
    path = STEPS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsPathTests(unittest.TestCase):
    def test_drive_path_converts_to_wsl_mount(self):
        mod = load_steps_module("smri_windows_utils.py")
        path = PureWindowsPath(r"D:\master\QC\sMRI_pipelineV2_win")
        self.assertEqual(mod.to_wsl_path(path), "/mnt/d/master/QC/sMRI_pipelineV2_win")

    def test_unc_path_is_rejected_for_wsl_mount_conversion(self):
        mod = load_steps_module("smri_windows_utils.py")
        with self.assertRaises(ValueError):
            mod.to_wsl_path(PureWindowsPath(r"\\10.19.136.231\002\CBCP"))


class CommandBuilderTests(unittest.TestCase):
    def test_python_step_command_uses_current_interpreter_and_script(self):
        mod = load_steps_module("smri_windows_utils.py")
        ctx = mod.PipelineContext(
            pipeline_dir=Path(r"D:\pipeline"),
            batch_dir=Path(r"D:\batch"),
            python_bin="py",
        )
        cmd = ctx.python_step("scripts/steps/11_write_preprocessing_report_v2.py", "--batch-dir", ctx.batch_dir)
        self.assertEqual(cmd[0], "py")
        self.assertEqual(cmd[1], str(Path(r"D:\pipeline") / "scripts/steps/11_write_preprocessing_report_v2.py"))
        self.assertEqual(cmd[-1], str(Path(r"D:\batch")))

    def test_wsl_bash_command_exports_nnunet_variables(self):
        mod = load_steps_module("smri_windows_utils.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pipeline_dir = root / "pipeline"
            batch_dir = root / "batch"
            pipeline_dir.mkdir()
            batch_dir.mkdir()
            ctx = mod.PipelineContext(
                pipeline_dir=pipeline_dir,
                batch_dir=batch_dir,
                wsl_distro="Ubuntu",
            )
            command = mod.build_wsl_bash_command(
                ctx,
                'bash "$PIPELINE_DIR/scripts/jobs/nnunet_task523.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
                nnunet_resource_dir=pipeline_dir / "resources" / "models" / "nnUNet",
            )
            self.assertEqual(command[:5], ["wsl.exe", "-d", "Ubuntu", "--", "/bin/bash"])
            generated = sorted((batch_dir / "logs" / "wsl_commands").glob("wsl_*.sh"))
            self.assertEqual(len(generated), 1)
            script = generated[0].read_text(encoding="utf-8")
            pipeline_wsl = mod.to_wsl_path(pipeline_dir)
            batch_wsl = mod.to_wsl_path(batch_dir)
            self.assertEqual(command[-1], mod.to_wsl_path(generated[0]))
            self.assertIn(f"export PIPELINE_DIR={pipeline_wsl}", script)
            self.assertIn(f"export BATCH_DIR={batch_wsl}", script)
            self.assertIn(f"export nnUNet_raw_data_base={pipeline_wsl}/resources/models/nnUNet/nnUNetData/nnUNet_raw_data_base", script)
            self.assertIn(f"export nnUNet_preprocessed={pipeline_wsl}/resources/models/nnUNet/nnUNetData/nnUNet_preprocessed", script)
            self.assertIn(f"export RESULTS_FOLDER={pipeline_wsl}/resources/models/nnUNet/nnUNetData/RESULTS_FOLDER", script)

    def test_docker_bash_command_mounts_pipeline_and_batch(self):
        mod = load_steps_module("smri_windows_utils.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pipeline_dir = root / "pipeline"
            batch_dir = root / "batch"
            pipeline_dir.mkdir()
            batch_dir.mkdir()
            ctx = mod.PipelineContext(pipeline_dir=pipeline_dir, batch_dir=batch_dir)
            command = mod.build_docker_bash_command(
                ctx,
                "smri_pipeline_win:ai-test",
                'echo "$PIPELINE_DIR" "$BATCH_DIR"',
                nnunet_resource_dir=pipeline_dir / "resources" / "models" / "nnUNet",
                gpus="all",
            )
            self.assertEqual(command[:4], ["docker", "run", "--rm", "--gpus"])
            self.assertIn("all", command)
            self.assertIn("smri_pipeline_win:ai-test", command)
            self.assertIn(f"{pipeline_dir.resolve()}:/pipeline", command)
            self.assertIn(f"{batch_dir.resolve()}:/batch", command)
            generated = sorted((batch_dir / "logs" / "docker_commands").glob("docker_*.sh"))
            self.assertEqual(len(generated), 1)
            script = generated[0].read_text(encoding="utf-8")
            self.assertIn("export PIPELINE_DIR=/pipeline", script)
            self.assertIn("export BATCH_DIR=/batch", script)
            self.assertIn("export nnUNet_raw_data_base=/pipeline/resources/models/nnUNet/nnUNetData/nnUNet_raw_data_base", script)
            self.assertIn("NNUNET_RESOURCE_DIR=/pipeline/resources/models/nnUNet", command)

    def test_docker_bash_command_uses_default_freesurfer_license(self):
        mod = load_steps_module("smri_windows_utils.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pipeline_dir = root / "pipeline"
            batch_dir = root / "batch"
            license_path = pipeline_dir / "resources" / "software" / "freesurfer" / "license.txt"
            license_path.parent.mkdir(parents=True)
            license_path.write_text("test-license\n", encoding="utf-8")
            batch_dir.mkdir()
            ctx = mod.PipelineContext(pipeline_dir=pipeline_dir, batch_dir=batch_dir)
            command = mod.build_docker_bash_command(ctx, "smri_pipeline_win:tools-test", "echo ok")
            self.assertIn("FS_LICENSE=/pipeline/resources/software/freesurfer/license.txt", command)
            self.assertNotIn(f"{license_path.resolve()}:/licenses/freesurfer/license.txt:ro", command)


    def test_docker_bash_command_accepts_extra_mounts_from_environment(self):
        mod = load_steps_module("smri_windows_utils.py")
        old_mounts = os.environ.get("SMRI_DOCKER_EXTRA_MOUNTS")
        os.environ["SMRI_DOCKER_EXTRA_MOUNTS"] = "D:\\tools\\fsl:/opt/fsl:ro;D:\\tools\\freesurfer:/opt/freesurfer:ro"
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                pipeline_dir = root / "pipeline"
                batch_dir = root / "batch"
                pipeline_dir.mkdir()
                batch_dir.mkdir()
                ctx = mod.PipelineContext(pipeline_dir=pipeline_dir, batch_dir=batch_dir)
                command = mod.build_docker_bash_command(ctx, "smri_pipeline_win:tools-test", 'echo ok')
                self.assertIn("D:\\tools\\fsl:/opt/fsl:ro", command)
                self.assertIn("D:\\tools\\freesurfer:/opt/freesurfer:ro", command)
        finally:
            if old_mounts is None:
                os.environ.pop("SMRI_DOCKER_EXTRA_MOUNTS", None)
            else:
                os.environ["SMRI_DOCKER_EXTRA_MOUNTS"] = old_mounts


    def test_presurf_only_returns_success_without_recon_code(self):
        path = REPO / "scripts/jobs/smri_presurf_recon_win.py"
        spec = importlib.util.spec_from_file_location("smri_presurf_recon_win", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = Path(temp) / "batch"
            (batch_dir / "6_seg" / "sub-001").mkdir(parents=True)
            calls = []
            old_run_step = mod.run_step
            old_write_report = mod.write_report
            try:
                mod.run_step = lambda *args, **kwargs: calls.append(args[1]) or 0
                mod.write_report = lambda *args, **kwargs: None
                code = mod.main([str(batch_dir), "--submit", "--presurf-only", "--presurf-backend", "windows"])
            finally:
                mod.run_step = old_run_step
                mod.write_report = old_write_report
            self.assertEqual(code, 0)
            self.assertEqual(calls, ["30_presurf_standard"])

    def test_moved_windows_dispatchers_run_help_from_repo_root(self):
        for relative in (
            "scripts/jobs/smri_preprocessing_win.py",
            "scripts/jobs/smri_presurf_recon_win.py",
        ):
            result = subprocess.run(
                [sys.executable, str(REPO / relative), "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()




