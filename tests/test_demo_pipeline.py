import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / "steps" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DicomSeriesSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("40_dicom_to_nifti_demo.py")

    def test_classifies_3d_mprage_as_t1(self):
        metadata = {
            "SeriesDescription": "t1_mprage_sag_p2_iso",
            "ProtocolName": "T1 MPRAGE",
            "MRAcquisitionType": "3D",
            "ImageType": ["ORIGINAL", "PRIMARY", "M", "ND"],
        }
        self.assertEqual(self.mod.classify_series(metadata), "t1")

    def test_classifies_3d_space_as_t2(self):
        metadata = {
            "SeriesDescription": "T2 SPACE SAG ISO",
            "ProtocolName": "T2w",
            "MRAcquisitionType": "3D",
            "ImageType": ["ORIGINAL", "PRIMARY", "M", "ND"],
        }
        self.assertEqual(self.mod.classify_series(metadata), "t2")

    def test_excludes_scout_motion_and_derived_series(self):
        cases = [
            {"SeriesDescription": "GRE Scout", "ImageType": ["ORIGINAL", "PRIMARY"]},
            {"SeriesDescription": "Motion Curve", "ImageType": ["ORIGINAL", "PRIMARY"]},
            {"SeriesDescription": "T1 MPRAGE", "ImageType": ["DERIVED", "SECONDARY"]},
        ]
        for metadata in cases:
            with self.subTest(metadata=metadata):
                self.assertEqual(self.mod.classify_series(metadata), "excluded")

    def test_excludes_ndc_t1_series(self):
        metadata = {
            "SeriesDescription": "t1w_A3.22_iso0.8mm_CBCP_NDC",
            "ProtocolName": "t1w_A3.22_iso0.8mm_CBCP",
            "MRAcquisitionType": "3D",
            "ImageType": ["ORIGINAL", "PRIMARY", "M", "UCA", "MAGNITUDE"],
        }
        self.assertEqual(self.mod.classify_series(metadata), "excluded")

    def test_selects_unique_highest_scoring_candidate(self):
        candidates = [
            self.mod.SeriesCandidate("001", "t1-low.nii.gz", "t1-low.json", "t1", 40),
            self.mod.SeriesCandidate("002", "t1-high.nii.gz", "t1-high.json", "t1", 70),
        ]
        self.assertEqual(self.mod.choose_series(candidates, "t1").series_number, "002")

    def test_refuses_equally_ranked_t1_candidates(self):
        candidates = [
            self.mod.SeriesCandidate("001", "t1-a.nii.gz", "t1-a.json", "t1", 70),
            self.mod.SeriesCandidate("002", "t1-b.nii.gz", "t1-b.json", "t1", 70),
        ]
        with self.assertRaises(self.mod.AmbiguousSeriesError):
            self.mod.choose_series(candidates, "t1")

    def test_explicit_series_number_resolves_ambiguity(self):
        candidates = [
            self.mod.SeriesCandidate("001", "t1-a.nii.gz", "t1-a.json", "t1", 70),
            self.mod.SeriesCandidate("002", "t1-b.nii.gz", "t1-b.json", "t1", 70),
        ]
        selected = self.mod.choose_series(candidates, "t1", requested_series="002")
        self.assertEqual(selected.nifti_path, "t1-b.nii.gz")

    def test_relative_raw_dir_is_resolved_under_batch(self):
        batch = Path("/data")
        self.assertEqual(
            self.mod.resolve_raw_dir(batch, "26_MRIdata"),
            batch / "26_MRIdata",
        )

    def test_inventory_only_keeps_ambiguous_candidates_without_standardizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            subject_dir = batch / "0_rawdata" / "001"
            subject_dir.mkdir(parents=True)
            candidate_dir = batch / "1_T2toT1" / "dicom_candidates" / "001"
            candidate_dir.mkdir(parents=True)
            for number in ("301", "302"):
                stem = candidate_dir / f"{number}_T1_MPRAGE"
                Path(str(stem) + ".nii.gz").write_bytes(b"nifti")
                Path(str(stem) + ".json").write_text(
                    json.dumps(
                        {
                            "SeriesNumber": number,
                            "SeriesDescription": "T1 MPRAGE",
                            "MRAcquisitionType": "3D",
                            "ImageType": ["ORIGINAL", "PRIMARY"],
                        }
                    ),
                    encoding="utf-8",
                )

            inventory, summary = self.mod.process_subject(
                subject_dir,
                batch,
                SimpleNamespace(
                    dcm2niix="dcm2niix",
                    t1_series=None,
                    t2_series=None,
                    force=False,
                    inventory_only=True,
                ),
            )

            self.assertEqual(len(inventory), 2)
            self.assertEqual(summary["status"], "inventory_complete")
            self.assertFalse((batch / "1_T2toT1" / "data" / "001" / "T1.nii.gz").exists())
            self.assertTrue(all(row["selected"] == "" for row in inventory))

    def test_dc3d_t1_ranks_above_ndc_t1(self):
        ndc = {
            "SeriesDescription": "t1w_iso0.8mm_NDC",
            "MRAcquisitionType": "3D",
            "ImageType": ["ORIGINAL", "PRIMARY", "M", "UCA", "MAGNITUDE"],
        }
        dc3d = {
            "SeriesDescription": "t1w_iso0.8mm",
            "MRAcquisitionType": "3D",
            "ImageType": ["ORIGINAL", "PRIMARY", "M", "UCA", "DC3D", "MAGNITUDE"],
        }
        self.assertGreater(
            self.mod.score_series(dc3d, "t1"), self.mod.score_series(ndc, "t1")
        )


class StandardReconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("41_check_standard_recon_demo.py")

    def test_complete_recon_requires_done_pial_and_brainmask(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "001"
            for relative in [
                "scripts/recon-all.done",
                "surf/lh.pial",
                "surf/rh.pial",
                "mri/brainmask.mgz",
                "mri/aseg.mgz",
            ]:
                path = subject / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"ok")
            self.assertTrue(self.mod.recon_done(subject))

    def test_recon_error_marker_overrides_done_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "001"
            for relative in [
                "scripts/recon-all.done",
                "surf/lh.pial",
                "surf/rh.pial",
                "mri/brainmask.mgz",
                "mri/aseg.mgz",
                "scripts/recon-all.error",
            ]:
                path = subject / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"error" if relative.endswith(".error") else b"ok")
            self.assertFalse(self.mod.recon_done(subject))

    def test_mris_volmask_license_tail_error_is_a_recoverable_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "001"
            for relative in [
                "scripts/recon-all.done",
                "surf/lh.pial",
                "surf/rh.pial",
                "mri/brainmask.mgz",
                "mri/aseg.mgz",
                "scripts/recon-all.error",
            ]:
                path = subject / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"ok")
            log = subject / "scripts" / "recon-all.log"
            log.write_text(
                "mris_volmask --parallel 001\n"
                "ERROR: Invalid FreeSurfer license key found in license file\n"
                "recon-all -s 001 exited with ERRORS\n",
                encoding="utf-8",
            )
            self.assertTrue(self.mod.recoverable_tail_warning(subject))
    def test_partial_surface_is_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "001"
            path = subject / "surf" / "lh.pial"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"partial")
            self.assertFalse(self.mod.recon_done(subject))

    def test_recon_shell_uses_standard_recon_all(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn("recon-all", text)
        self.assertIn("-T2pial", text)
        self.assertIn("-all", text)
        self.assertNotIn("infant_recon_all", text)
        self.assertNotIn("--segfile", text)

    def test_recon_shell_supports_explicit_subject_filter(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn("REQUESTED_SUBJECTS", text)

    def test_recon_shell_checks_t2_before_enabling_t2pial(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn("43_t2_pial_policy_demo.py", text)

    def test_recon_shell_can_resume_stale_container_lock(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn("IsRunning.lh+rh", text)
        self.assertIn("-no-isrunning", text)
        self.assertIn("kill -0", text)

    def test_recon_avoids_fs81_mris_volmask_parallel_license_bug(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn('-openmp "$RECON_THREADS"', text)
        self.assertNotIn('recon_args+=(-parallel', text)

    def test_recon_preserves_recoverable_mris_volmask_warning(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn("recoverable_tail_warning", text)
        self.assertIn("teaching outputs complete", text)
        self.assertIn("CMD mris_volmask", text)

    def test_recon_repairs_stale_fsaverage_symlink(self):
        text = (ROOT / "scripts" / "jobs" / "recon_all_demo.sh").read_text(encoding="utf-8")
        self.assertIn('fsaverage_link="${SUBJECTS_DIR}/fsaverage"', text)
        self.assertIn('[ -L "$fsaverage_link" ]', text)
        self.assertIn('rm -f "$fsaverage_link"', text)
        self.assertIn('ln -s "$fsaverage_target" "$fsaverage_link"', text)
        self.assertIn('recon-all.error', text)


class T2PialPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("43_t2_pial_policy_demo.py")

    def test_accepts_3d_t2(self):
        metadata = {
            "MRAcquisitionType": "3D",
            "SliceThickness": 0.8,
            "SpacingBetweenSlices": 0.8,
        }
        self.assertTrue(self.mod.is_t2_pial_candidate(metadata))

    def test_rejects_2d_thick_slice_t2(self):
        metadata = {
            "MRAcquisitionType": "2D",
            "SliceThickness": 5,
            "SpacingBetweenSlices": 6.5,
        }
        self.assertFalse(self.mod.is_t2_pial_candidate(metadata))

    def test_policy_source_is_compatible_with_container_python36(self):
        source = (ROOT / "scripts" / "steps" / "43_t2_pial_policy_demo.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from __future__ import annotations", source)


class DicomConversionCompatibilityTests(unittest.TestCase):
    def test_converter_source_is_compatible_with_container_python36(self):
        source = (ROOT / "scripts" / "steps" / "40_dicom_to_nifti_demo.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from __future__ import annotations", source)


class ActiveWorkflowTests(unittest.TestCase):
    def test_slim_controller_does_not_expose_fsl_registration(self):
        shell = (ROOT / "scripts" / "jobs" / "smri_reconstruction_demo.sh").read_text(encoding="utf-8")
        self.assertNotIn("--registration", shell)
        self.assertNotIn("sMRI_pipeline_step0_reg2_v2.sh", shell)


class StlExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("42_export_pial_stl_demo.py")

    def test_builds_left_right_and_combined_surface_commands(self):
        subject_dir = Path("/subjects/001")
        output_dir = Path("/output/001")
        commands = self.mod.build_commands(subject_dir, output_dir, "mris_convert")
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[0][-2:], [str(subject_dir / "surf/lh.pial"), str(output_dir / "lh.pial.stl")])
        self.assertIn("--combinesurfs", commands[2])
        self.assertEqual(commands[2][-1], str(output_dir / "brain.pial.stl"))

    def test_stl_checkpoint_requires_all_three_nonempty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for name in ("lh.pial.stl", "rh.pial.stl", "brain.pial.stl"):
                (output / name).write_bytes(b"solid")
            self.assertTrue(self.mod.stl_done(output))
            (output / "brain.pial.stl").unlink()
            self.assertFalse(self.mod.stl_done(output))

    def test_default_subject_discovery_uses_input_data_not_fsaverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recon_root = root / "3_recon"
            input_root = root / "1_T2toT1" / "data"
            for name in ("001", "003"):
                (input_root / name).mkdir(parents=True)
                (recon_root / name).mkdir(parents=True)
            (recon_root / "fsaverage").mkdir(parents=True)
            discovered = self.mod.discover_subject_dirs(recon_root, input_root, [])
            self.assertEqual([path.name for path in discovered], ["001", "003"])
    def test_stl_job_tolerates_nonzero_freesurfer_setup_tail_command(self):
        text = (ROOT / "scripts" / "jobs" / "export_stl_demo.sh").read_text(encoding="utf-8")
        self.assertIn('source "${FREESURFER_HOME}/SetUpFreeSurfer.sh" || true', text)



class DemoEntrypointTests(unittest.TestCase):
    def test_container_image_uses_freesurfer_only_base(self):
        text = (ROOT / "docker" / "Dockerfile.smri-demo").read_text(encoding="utf-8")
        self.assertIn("FROM freesurfer/freesurfer:8.1.0", text)
        self.assertIn("dcm2niix", text)
        self.assertIn("COPY --from=dcm2niix-source /opt/fsl/bin/dcm2niix", text)
        self.assertIn("COPY", text)
        self.assertIn("ENTRYPOINT", text)
        self.assertNotIn("FSLDIR", text)

    def test_docker_context_excludes_local_image_cache(self):
        patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("docker/.cache/", patterns)

    def test_slim_doctor_does_not_require_fsl(self):

        text = (ROOT / "docker" / "demo_entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("flirt", text)
    def test_linux_controller_skips_research_only_stages(self):
        text = (ROOT / "scripts" / "jobs" / "smri_reconstruction_demo.sh").read_text(encoding="utf-8")
        self.assertIn("40_dicom_to_nifti_demo.py", text)
        self.assertIn("recon_all_demo.sh", text)
        self.assertNotIn("nnunet", text.lower())
        self.assertNotIn("presurf", text.lower())
        self.assertNotIn("acpc", text.lower())

    def test_windows_reconstruction_launcher_mounts_host_data(self):
        text = (ROOT / "bin" / "smri_reconstruction.ps1").read_text(encoding="utf-8")
        self.assertIn(":/data", text)
        self.assertIn("caibility1/smri_pipeline_demo", text)
        self.assertIn("FS_LICENSE", text)

    def test_dcm2niix_only_is_an_inventory_stage(self):
        shell = (ROOT / "scripts" / "jobs" / "smri_reconstruction_demo.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "bin" / "smri_reconstruction.ps1").read_text(encoding="utf-8")
        self.assertIn("--dcm2niix-only", shell)
        self.assertIn('DICOM_ARGS+=("--inventory-only")', shell)
        self.assertIn("--dcm2niix-only", launcher)

    def test_select_only_standardizes_qc_choices_without_starting_recon(self):
        shell = (ROOT / "scripts" / "jobs" / "smri_reconstruction_demo.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "bin" / "smri_reconstruction.ps1").read_text(encoding="utf-8")
        self.assertIn("--select-only", shell)
        self.assertIn("SELECT_ONLY=1", shell)
        self.assertIn('if [ "$SELECT_ONLY" -eq 1 ]', shell)
        self.assertIn("--select-only", launcher)

    def test_setup_creates_environment_directory_in_slim_clone(self):
        text = (ROOT / "setup_demo.ps1").read_text(encoding="utf-8")
        self.assertIn('$EnvironmentDir = Join-Path $RepoRoot "environment"', text)
        self.assertIn("New-Item -ItemType Directory -Force -Path $EnvironmentDir", text)

    def test_windows_stl_launcher_calls_stl_command(self):
        text = (ROOT / "bin" / "smri_3d_print.ps1").read_text(encoding="utf-8")
        self.assertIn(":/data", text)
        self.assertIn('"stl"', text)


    def test_offline_bundle_exports_image_code_and_checksums(self):
        text = (ROOT / "docker" / "export_demo_offline_bundle.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("docker save", text)
        self.assertIn("git -C $RepoRoot archive", text)
        self.assertIn("Get-FileHash -Algorithm SHA256", text)

    def test_student_quickstart_supports_offline_import(self):
        text = (ROOT / "docs" / "student_quickstart.md").read_text(encoding="utf-8")
        self.assertIn("docker load", text)
        self.assertIn("--dcm2niix-only", text)
        self.assertIn("--select-only", text)
        self.assertIn("--skip-dicom", text)

class CodespacesEntrypointTests(unittest.TestCase):
    def test_codespaces_uses_published_prebuild_image_without_nested_docker(self):
        config = json.loads(
            (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["image"],
            "caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23",
        )
        self.assertTrue(config["overrideCommand"])
        self.assertNotIn("hostRequirements", config)
        self.assertNotIn("features", config)

    def test_cloud_image_flattens_freesurfer_without_matlab_runtime(self):
        text = (ROOT / "docker" / "Dockerfile.smri-demo-cloud").read_text(
            encoding="utf-8"
        )
        self.assertIn("FROM freesurfer/freesurfer:8.1.0 AS freesurfer-source", text)
        self.assertIn("RUN --mount=from=freesurfer-source", text)
        self.assertIn("--exclude='./MCRv97'", text)
        self.assertIn("FROM rockylinux:8", text)
        self.assertNotIn("fs_install_mcr", text)
        for tool in ("python3", "dcm2niix", "recon-all", "mris_convert", "tcsh"):
            self.assertIn(f"command -v {tool}", text)

    def test_post_create_reports_resources_and_next_linux_command(self):
        text = (ROOT / ".devcontainer" / "post_create.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("nproc", text)
        self.assertIn("free -h", text)
        self.assertIn("df -h", text)
        self.assertIn("smri_reconstruction.sh", text)

    def test_linux_launchers_delegate_to_existing_demo_jobs(self):
        reconstruct = (ROOT / "bin" / "smri_reconstruction.sh").read_text(
            encoding="utf-8"
        )
        stl = (ROOT / "bin" / "smri_3d_print.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/jobs/smri_reconstruction_demo.sh", reconstruct)
        self.assertIn("scripts/jobs/export_stl_demo.sh", stl)
        self.assertIn("PIPELINE_DIR", reconstruct)
        self.assertIn("PIPELINE_DIR", stl)

    def test_cloud_data_and_license_are_not_committed(self):
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("cloud_data/", patterns)
        self.assertIn(".secrets/", patterns)

    def test_codespaces_tutorial_has_complete_two_stage_workflow(self):
        text = (ROOT / "docs" / "codespaces_student_tutorial.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("--dcm2niix-only", text)
        self.assertIn("--select-only", text)
        self.assertIn("--skip-dicom", text)
        self.assertIn("smri_3d_print.sh", text)
        self.assertIn("de-identified", text)
        self.assertIn("8 cores", text)
        self.assertIn("32 GB", text)
        self.assertIn("4-core, 16 GB", text)
if __name__ == "__main__":
    unittest.main()
