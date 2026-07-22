import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class PortableDockerFileTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (REPO / relative).read_text(encoding="utf-8")

    def test_ai_image_contains_both_model_contexts(self):
        text = self.read("docker/Dockerfile.smri-ai-portable")
        self.assertIn("FROM smri_pipeline_win:ai", text)
        self.assertIn("COPY --from=nnunet", text)
        self.assertIn("/opt/smri/models/nnUNet", text)
        self.assertIn("COPY --from=moardiff", text)
        self.assertIn("/opt/smri/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune", text)
        self.assertNotIn("license.txt", text)

    def test_tools_image_combines_existing_tools_and_freesurfer(self):
        text = self.read("docker/Dockerfile.smri-tools-portable")
        self.assertIn("FROM freesurfer/freesurfer:8.1.0 AS freesurfer", text)
        self.assertIn("FROM smri_pipeline_win:tools", text)
        self.assertIn("COPY --from=freesurfer", text)
        self.assertIn("COPY --from=fsl", text)
        self.assertIn("COPY --from=workbench", text)
        self.assertIn("COPY --from=templates", text)
        self.assertIn("FSLDIR=/opt/fsl", text)
        self.assertIn("FREESURFER_HOME=/opt/freesurfer", text)
        self.assertNotIn("license.txt", text)

    def test_build_script_uses_named_resource_contexts(self):
        text = self.read("docker/build_portable_images.ps1")
        for name in ("nnunet", "moardiff", "workbench", "templates", "fsl"):
            self.assertIn(f"--build-context {name}=", text)
        self.assertIn("smri_pipeline_win:ai-portable", text)
        self.assertIn("smri_pipeline_win:tools-portable", text)
        self.assertIn("type=docker,compression=uncompressed", text)

    def test_fsl_context_is_imported_from_a_wsl_tar_archive(self):
        prepare = self.read("docker/prepare_fsl_context.ps1")
        build = self.read("docker/build_portable_images.ps1")
        self.assertIn("wsl.exe", prepare)
        self.assertIn("tar", prepare)
        self.assertIn("docker", prepare)
        self.assertIn("import", prepare)
        self.assertIn("smri-fsl-context:6.0.7.22", prepare)
        self.assertIn('"smri-fsl-context:6.0.7.22"', build)
        self.assertIn('"docker-image://$FslContextImage"', build)
        self.assertIn("$PrepareArgs = @{", build)
        self.assertNotIn('"-WslDistro", $WslDistro', build)


    def test_full_image_contains_ai_tools_and_all_resources(self):
        text = self.read("docker/Dockerfile.smri-full-portable")
        self.assertIn("FROM smri_pipeline_win:ai AS ai", text)
        self.assertIn("FROM smri_pipeline_win:tools AS tools", text)
        self.assertIn("FROM freesurfer/freesurfer:8.1.0", text)
        self.assertNotIn("COPY --from=freesurfer", text)
        self.assertIn("/usr/local/freesurfer/8.1.0-1", text)
        self.assertIn("import torch", text)
        for name in ("nnunet", "moardiff", "fsl", "workbench", "templates"):
            self.assertIn(f"COPY --from={name}", text)
        self.assertIn("/opt/smri/models/nnUNet", text)
        self.assertIn("FSLDIR=/opt/fsl", text)
        self.assertIn("FREESURFER_HOME=/opt/freesurfer", text)
        self.assertNotIn("COPY license.txt", text)


    def test_publish_script_uses_versioned_docker_hub_tags(self):
        text = self.read("docker/publish_portable_images.ps1")
        self.assertIn('[string]$Registry = "caibility1/smri_pipeline_win"', text)
        self.assertIn('"full-$Release"', text)
        self.assertIn("docker", text)
        self.assertIn("push", text)
        self.assertNotIn("Run: docker login ghcr.io", text)
        self.assertIn("selected registry", text)

    def test_install_script_pulls_materializes_and_copies_license(self):
        text = self.read("docker/install_portable.ps1")
        self.assertIn('[string]$Registry = "caibility1/smri_pipeline_win"', text)
        self.assertIn("docker", text)
        self.assertIn("pull", text)
        self.assertIn("docker cp", text)
        self.assertIn("resources\\models\\nnUNet", text)
        self.assertIn("resources\\models\\denoise_diffusion", text)
        self.assertIn("resources\\software\\workbench-linux64-v2.0.0\\workbench", text)
        self.assertIn("resources\\templates", text)
        self.assertIn("resources\\software\\freesurfer\\license.txt", text)
        self.assertIn("/usr/local/freesurfer/license.txt", text)
        self.assertIn("SMRI_DOCKER_BUNDLED_RESOURCES", text)
        self.assertIn("function Test-NativeProbe", text)


    def test_install_script_can_reuse_an_existing_local_image(self):
        text = self.read("docker/install_portable.ps1")
        self.assertIn("[switch]$UseLocalImage", text)
        self.assertIn("if ($UseLocalImage)", text)
        self.assertIn("Using existing local image", text)
        self.assertIn("docker image inspect $LocalImage", text)

    def test_windows_core_environment_excludes_ai_runtime(self):
        text = self.read("environment/windows-core.yml").lower()
        self.assertIn("name: smri_pipeline_win", text)
        self.assertIn("nibabel", text)
        self.assertIn("simpleitk", text)
        self.assertNotIn("pytorch", text)
        self.assertNotIn("nnunet", text)

    def test_new_machine_setup_covers_host_prerequisites_and_pipeline_setup(self):
        text = self.read("setup_new_machine.ps1")
        self.assertIn("wsl.exe", text)
        self.assertIn("Docker.DockerDesktop", text)
        self.assertIn("CondaForge.Miniforge3", text)
        self.assertIn("windows-core.yml", text)
        self.assertIn("docker\\install_portable.ps1", text)
        self.assertIn("docker\\doctor.ps1", text)
        self.assertIn("function Test-NativeProbe", text)
        self.assertIn("Docker Desktop is installed but its Linux engine is not running", text)
        self.assertIn("--no-distribution", text)
        self.assertNotIn("wsl.exe -d $WslDistro -- true", text)
        self.assertIn("[switch]$UseLocalImage", text)
        self.assertIn("if ($UseLocalImage) { $InstallArgs.UseLocalImage = $true }", text)
        self.assertIn("[string]$Registry", text)
        self.assertIn('[string]$Registry = "caibility1/smri_pipeline_win"', text)
        self.assertIn("Registry = $Registry", text)

    def test_cmd_bootstrap_bypasses_policy_for_setup_process_only(self):
        text = self.read("setup_new_machine.cmd")
        self.assertIn("powershell.exe", text.lower())
        self.assertIn("-NoProfile", text)
        self.assertIn("-ExecutionPolicy Bypass", text)
        self.assertIn('-File "%~dp0setup_new_machine.ps1"', text)
        self.assertIn("%*", text)
        self.assertIn("exit /b %ERRORLEVEL%", text)

    def test_new_machine_setup_finds_conda_without_shell_initialization(self):
        text = self.read("setup_new_machine.ps1")
        self.assertIn("function Resolve-CondaExecutable", text)
        self.assertIn("miniforge3\\Scripts\\conda.exe", text)
        self.assertIn("miniconda3\\Scripts\\conda.exe", text)
        self.assertIn("anaconda3\\Scripts\\conda.exe", text)
        self.assertIn("$Conda = Resolve-CondaExecutable", text)
        self.assertIn("& $Conda env list --json", text)
        self.assertIn("$EnvironmentPath =", text)
        self.assertIn("$Python = Join-Path $EnvironmentPath \"python.exe\"", text)
        self.assertNotIn("& $Conda run -n $EnvironmentName python", text)

    def test_bin_entrypoints_are_runtime_only(self):
        for relative in ("bin/smri_preprocessing.ps1", "bin/smri_presurf_recon.ps1"):
            text = self.read(relative)
            self.assertIn("docker", text.lower())
            self.assertIn("SMRI_RUNTIME_IMAGE", text)
            self.assertNotIn("windows_env.local.ps1", text)
            self.assertNotIn("SMRI_PYTHON", text)

    def test_full_image_bundles_runtime_code_and_entrypoint(self):
        text = self.read("docker/Dockerfile.smri-full-portable")
        self.assertIn("COPY scripts /opt/smri/pipeline/scripts", text)
        self.assertIn("COPY docker/runtime_entrypoint.sh", text)
        self.assertIn("ENTRYPOINT", text)
        self.assertIn("SMRI_CONTAINER_RUNTIME=1", text)

    def test_container_runtime_replaces_nested_docker_jobs(self):
        text = self.read("scripts/jobs/smri_container_runtime.py")
        self.assertIn("def run_native_job", text)
        self.assertIn("module.run_docker_job = run_native_job", text)
        self.assertIn("container-native", text)

    def test_cmd_companions_launch_powershell_with_bypass(self):
        for relative in ("bin/smri_preprocessing.cmd", "bin/smri_presurf_recon.cmd"):
            text = self.read(relative)
            self.assertIn("ExecutionPolicy Bypass", text)
            self.assertIn("%*", text)
            self.assertIn("exit /b %ERRORLEVEL%", text)
    def test_runtime_maintenance_scripts_use_readable_tags(self):
        build = self.read("docker/build_runtime_image.ps1")
        publish = self.read("docker/publish_runtime_image.ps1")
        doctor = self.read("docker/doctor_runtime.ps1")
        self.assertIn("smri_pipeline_win:runtime-test", build)
        self.assertIn("runtime-v2-2026-07-22", publish)
        self.assertIn("runtime-v2-2026-07-22", doctor)
        self.assertIn("docker push", publish)
        self.assertIn('"doctor"', doctor)

    def test_runtime_build_accepts_external_resource_root(self):
        text = self.read("docker/build_runtime_image.ps1")
        self.assertIn("$ResourceRoot", text)
        for name in ("nnunet", "moardiff", "workbench", "templates"):
            self.assertIn(f'"--build-context", "{name}=', text)


    def test_runtime_launcher_preserves_single_license_candidate_as_array(self):
        text = self.read("scripts/steps/smri_docker_launcher.ps1")
        self.assertIn("$LicenseCandidates = @(@(", text)



    def test_doctor_checks_bundled_resources_and_tools(self):
        text = self.read("docker/doctor.ps1")
        self.assertIn("SMRI_DOCKER_BUNDLED_RESOURCES", text)
        self.assertIn("/opt/smri/models/nnUNet", text)
        self.assertIn("MOARDIFF_CKPT", text)
        self.assertIn("SMRI_TEMPLATE_DIR", text)
        self.assertIn("infant_recon_all", text)


    def test_portable_setup_sets_and_dispatchers_read_backend_defaults(self):
        installer = self.read("docker/install_portable.ps1")
        preprocessing = self.read("scripts/jobs/smri_preprocessing_win.py")
        postprocessing = self.read("scripts/jobs/smri_presurf_recon_win.py")
        for name in ("SMRI_REGISTRATION_BACKEND", "SMRI_NNUNET_BACKEND", "SMRI_MASK_BACKEND", "SMRI_ACPC_BACKEND", "SMRI_DENOISE_BACKEND"):
            self.assertIn(name, installer)
            self.assertIn(name, preprocessing)
        for name in ("SMRI_PRESURF_BACKEND", "SMRI_RECON_BACKEND"):
            self.assertIn(name, installer)
            self.assertIn(name, postprocessing)


if __name__ == "__main__":
    unittest.main()
