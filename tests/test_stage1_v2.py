import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STEPS = REPO / "scripts" / "steps"


def load_script(name):
    path = STEPS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stage1NamingTests(unittest.TestCase):
    def test_clean_subject_name_only_removes_trailing_age(self):
        mod = load_script("2_add_age_suffix_v2.py")
        self.assertEqual(mod.clean_subject_name("N1021_0101010002_3mo"), "N1021_0101010002")
        self.assertEqual(mod.clean_subject_name("N1021_0101010002_extra"), "N1021_0101010002_extra")
        self.assertEqual(mod.parse_age_suffix("0101010001_123mo"), ("0101010001", "123"))

    def test_nnunet_case_id_removes_internal_underscores_before_channel_suffix(self):
        mod = load_script("3_prepare_nnunet_input_v2.py")
        case_id = mod.make_case_id("N1021_0101010002_3mo")
        self.assertEqual(case_id, "T523_N102101010100023mo")
        self.assertEqual(mod.make_input_name(case_id), "T523_N102101010100023mo_0000.nii.gz")
        self.assertNotIn("_", case_id.removeprefix("T523_"))

    def test_numeric_excel_ids_normalize_decimal_and_leading_zero(self):
        age_mod = load_script("2_add_age_suffix_v2.py")
        qc_mod = load_script("10_select_denoise_candidates_v2.py")
        self.assertEqual(age_mod.normalize_id("0101010268"), "101010268")
        self.assertEqual(age_mod.normalize_id("101010268.0"), "101010268")
        self.assertEqual(age_mod.normalize_id("1.01010268E+8"), "101010268")
        self.assertEqual(qc_mod.normalize_id("101010268.0"), "101010268")

    def test_existing_age_suffix_can_replace_age_excel(self):
        mod = load_script("2_add_age_suffix_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            data = batch / "1_T2toT1" / "data"
            (data / "external001_24mo").mkdir(parents=True)
            result = mod.main(["--batch-dir", str(batch), "--age-source", "folder"])
            summary = (batch / "manifests" / "00_age_summary.csv").read_text(encoding="utf-8")
        self.assertEqual(result, 0)
        self.assertIn("external001_24mo", summary)
        self.assertIn("24", summary)


class Stage1FileTests(unittest.TestCase):
    def test_age_column_aliases_accept_month_variants(self):
        import pandas as pd

        mod = load_script("2_add_age_suffix_v2.py")
        df = pd.DataFrame({"participant_id": ["0101010268"], "age_months": ["67"]})
        self.assertEqual(mod.detect_columns(df), ("participant_id", "age_months"))
        df = pd.DataFrame({"受试者编号": ["0101010268"], "月": ["67"]})
        self.assertEqual(mod.detect_columns(df), ("受试者编号", "月"))

    def test_standardize_detects_multiple_t1_candidates(self):
        mod = load_script("1_standardize_t1_t2_v2.py")
        with tempfile.TemporaryDirectory() as td:
            subject = Path(td) / "sub001"
            subject.mkdir()
            (subject / "t1w_a.nii.gz").write_bytes(b"1")
            (subject / "T1_other.nii.gz").write_bytes(b"1")
            (subject / "t2w_a.nii.gz").write_bytes(b"2")
            result = mod.inspect_subject(subject)
        self.assertEqual(result.status, "failed")
        self.assertIn("multiple T1", result.error)

    def test_standardize_accepts_mixed_subject_naming_across_batch(self):
        mod = load_script("1_standardize_t1_t2_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            data = batch / "1_T2toT1" / "data"
            ready = data / "already_ready"
            raw = data / "raw_names"
            ready.mkdir(parents=True)
            raw.mkdir()
            (ready / "T1.nii.gz").write_bytes(b"1")
            (ready / "T2.nii.gz").write_bytes(b"2")
            (raw / "t1w_raw.nii.gz").write_bytes(b"1")
            (raw / "t2w_raw.nii.gz").write_bytes(b"2")
            failures = mod.process(data, batch / "manifests" / "summary.csv")
            self.assertEqual(failures, 0)
            self.assertTrue((ready / "T1.nii.gz").exists())
            self.assertTrue((raw / "T1.nii.gz").exists())
            self.assertTrue((raw / "T2.nii.gz").exists())

    def test_dataset_json_contains_batch_images(self):
        mod = load_script("3_prepare_nnunet_input_v2.py")
        payload = mod.build_dataset_json(["T523_A_0000.nii.gz", "T523_B_0000.nii.gz"])
        self.assertEqual(payload["numTest"], 2)
        self.assertEqual(payload["test"], ["./imagesTs/T523_A_0000.nii.gz", "./imagesTs/T523_B_0000.nii.gz"])
        self.assertEqual(payload["modality"], {"0": "T1"})

    def test_nnunet_prepare_dry_run_does_not_copy_images(self):
        mod = load_script("3_prepare_nnunet_input_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            subject = batch / "1_T2toT1" / "data" / "0101010001_2mo"
            subject.mkdir(parents=True)
            (subject / "T1.nii.gz").write_bytes(b"fake")
            failures = mod.process(batch, dry_run=True)
            images = list((batch / "2_nnunet_input" / "imagesTs").glob("*.nii.gz"))
            mapping = (batch / "2_nnunet_input" / "nnunet_id_map.csv").read_text(encoding="utf-8")
        self.assertEqual(failures, 0)
        self.assertEqual(images, [])
        self.assertIn("would_copy", mapping)


class Stage1MaskTests(unittest.TestCase):
    def test_shape_mismatch_is_reported_before_masking(self):
        mod = load_script("6_mask_all_v2.py")
        self.assertEqual(mod.shape_status((2, 2, 2), (2, 2, 3)), "shape_mismatch")
        self.assertEqual(mod.shape_status((2, 2, 2), (2, 2, 2)), "ok")


class Stage1NnunetCheckTests(unittest.TestCase):
    def test_require_all_fails_for_empty_map(self):
        mod = load_script("5_check_nnunet_outputs_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            map_dir = batch / "2_nnunet_input"
            map_dir.mkdir(parents=True)
            (map_dir / "nnunet_id_map.csv").write_text(
                "subject_name,nnunet_case_id,expected_mask\n",
                encoding="utf-8",
            )
            result = mod.main(["--batch-dir", str(batch), "--require-all"])
        self.assertEqual(result, 1)

    def test_require_all_succeeds_when_masks_exist(self):
        mod = load_script("5_check_nnunet_outputs_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            output = batch / "2_nnunet_output"
            output.mkdir(parents=True)
            mask = output / "T523_A.nii.gz"
            mask.write_bytes(b"mask")
            map_dir = batch / "2_nnunet_input"
            map_dir.mkdir(parents=True)
            (map_dir / "nnunet_id_map.csv").write_text(
                f"subject_name,nnunet_case_id,expected_mask\nsub,T523_A,{mask}\n",
                encoding="utf-8",
            )
            result = mod.main(["--batch-dir", str(batch), "--require-all"])
        self.assertEqual(result, 0)


class PreprocessingStage2Tests(unittest.TestCase):
    def test_split_for_acpc_creates_only_needed_branches(self):
        mod = load_script("7_split_for_acpc_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            t1t2 = batch / "3_skullstrip" / "data" / "sub_a_2mo"
            t1only = batch / "3_skullstrip" / "data" / "sub_b_3mo"
            t1t2.mkdir(parents=True)
            t1only.mkdir()
            for name in ["T1.nii.gz", "T2.nii.gz", "mask.nii.gz"]:
                (t1t2 / name).write_bytes(b"x")
            for name in ["T1.nii.gz", "mask.nii.gz"]:
                (t1only / name).write_bytes(b"x")
            rows = mod.process(batch)
            self.assertEqual({row["branch"] for row in rows}, {"T1T2", "justT1"})
            self.assertTrue((batch / "4_results" / "T1T2" / "sub_a_2mo" / "T2.nii.gz").exists())
            self.assertTrue((batch / "4_results" / "justT1" / "sub_b_3mo" / "T1.nii.gz").exists())

    def test_split_for_acpc_repairs_existing_subject_missing_input_files(self):
        mod = load_script("7_split_for_acpc_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            src = batch / "3_skullstrip" / "data" / "sub_a_2mo"
            dst = batch / "4_results" / "T1T2" / "sub_a_2mo"
            src.mkdir(parents=True)
            dst.mkdir(parents=True)
            for name in ["T1.nii.gz", "T2.nii.gz", "mask.nii.gz"]:
                (src / name).write_bytes(name.encode("ascii"))
            (dst / "T1.nii.gz").write_bytes(b"existing")
            rows = mod.process(batch)
            row = rows[0]
            self.assertEqual(row["status"], "repaired")
            self.assertEqual((dst / "T1.nii.gz").read_bytes(), b"existing")
            self.assertEqual((dst / "T2.nii.gz").read_bytes(), b"T2.nii.gz")
            self.assertEqual((dst / "mask.nii.gz").read_bytes(), b"mask.nii.gz")

    def test_split_for_acpc_fails_on_zero_size_existing_target_file(self):
        mod = load_script("7_split_for_acpc_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            src = batch / "3_skullstrip" / "data" / "sub_a_2mo"
            dst = batch / "4_results" / "T1T2" / "sub_a_2mo"
            src.mkdir(parents=True)
            dst.mkdir(parents=True)
            for name in ["T1.nii.gz", "T2.nii.gz", "mask.nii.gz"]:
                (src / name).write_bytes(b"x")
            (dst / "T1.nii.gz").write_bytes(b"")
            rows = mod.process(batch)
            row = rows[0]
            self.assertEqual(row["status"], "failed")
            self.assertIn("zero-size existing target", row["error"])
            self.assertEqual((dst / "T1.nii.gz").read_bytes(), b"")

    def test_questionable_status_normalization_selects_fail_and_questionable(self):
        mod = load_script("10_select_denoise_candidates_v2.py")
        self.assertEqual(mod.normalize_status("Pass"), "pass")
        self.assertEqual(mod.normalize_status("Fail"), "fail")
        self.assertEqual(mod.normalize_status("Questionable"), "questionable")

    def test_visual_qc_column_aliases_accept_external_names(self):
        import pandas as pd

        mod = load_script("10_select_denoise_candidates_v2.py")
        df = pd.DataFrame({"participant_id": ["0101010268"], "T1_visual_QC": ["pass"]})
        self.assertEqual(mod.detect_id_t1_columns(df), ("participant_id", "T1_visual_QC"))
        df = pd.DataFrame({"受试者编号": ["0101010268"], "QC status": ["pass"]})
        self.assertEqual(mod.detect_id_t1_columns(df), ("受试者编号", "QC status"))

    def test_questionable_cbcp_site_handles_stripped_leading_zero(self):
        mod = load_script("10_select_denoise_candidates_v2.py")
        self.assertEqual(mod.classify_cbcp_site("0101010268_67mo"), "skd")
        self.assertEqual(mod.classify_cbcp_site("101010268_67mo"), "skd")
        self.assertEqual(mod.classify_cbcp_site("0401010001_0mo"), "cz")
        self.assertEqual(mod.classify_cbcp_site("401010001_0mo"), "cz")

    def test_questionable_all_pass_mode_skips_denoise_selection(self):
        mod = load_script("10_select_denoise_candidates_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            subject = batch / "4_results" / "justT1" / "external001_24mo"
            subject.mkdir(parents=True)
            rows = mod.process_all_pass(batch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["qc_status"], "pass")
        self.assertEqual(rows[0]["status"], "pass_not_selected")
        self.assertEqual(rows[0]["source_sheet"], "all-pass")

    def test_questionable_input_is_flat_t1_only(self):
        import nibabel as nib
        import numpy as np

        mod = load_script("10_select_denoise_candidates_v2.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "4_results" / "T1T2" / "N1007_0302010494_0mo"
            dst = root / "5_questionable" / "input" / "N1007_0302010494_0mo"
            src.mkdir(parents=True)
            data = np.zeros((6, 7, 5), dtype=np.float32)
            data[1:5, 1:6, 1:4] = 1
            nib.Nifti1Image(data, np.eye(4)).to_filename(src / "T1_acpc.nii.gz")
            (src / "T2_acpc.nii.gz").write_bytes(b"t2")
            (src / "mask.nii.gz").write_bytes(b"mask")
            mod.prepare_input(src, dst, target_shape=(6, 7, 5))
            self.assertTrue((dst / "T1.nii.gz").exists())
            self.assertFalse((dst / "T2_acpc.nii.gz").exists())
            self.assertFalse((dst / "mask.nii.gz").exists())

    def test_questionable_input_is_cropped_and_padded_for_moardiff(self):
        import nibabel as nib
        import numpy as np

        mod = load_script("10_select_denoise_candidates_v2.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "4_results" / "T1T2" / "0101010268_67mo"
            dst = root / "5_questionable" / "input" / "0101010268_67mo"
            src.mkdir(parents=True)
            data = np.zeros((8, 10, 7), dtype=np.float32)
            data[2:5, 3:7, 1:4] = 9
            nib.Nifti1Image(data, np.eye(4)).to_filename(src / "T1_acpc.nii.gz")
            result = mod.prepare_input(src, dst, target_shape=(6, 7, 5))
            out = nib.load(dst / "T1.nii.gz").get_fdata()
            self.assertEqual(result["raw_shape"], "8x10x7")
            self.assertEqual(result["input_shape"], "6x7x5")
            self.assertEqual(out.shape, (6, 7, 5))
            self.assertEqual(int((out == 9).sum()), 36)

    def test_moardiff_subject_age_parser_uses_trailing_suffix(self):
        mod = load_script("21_run_moardiff_denoise_v2.py")
        subject_id, age, error = mod.parse_subject("A_B_C_12mo")
        self.assertEqual(subject_id, "A_B_C")
        self.assertEqual(age, "12")
        self.assertEqual(error, "")

    def test_moardiff_final_copies_raw_tree_and_replaces_t1_acpc(self):
        import nibabel as nib
        import numpy as np

        mod = load_script("21_run_moardiff_denoise_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            subject = "0101010268_67mo"
            raw = batch / "5_questionable" / "raw" / subject
            output = batch / "5_questionable" / "output" / subject
            input_dir = batch / "5_questionable" / "input" / subject
            final = batch / "5_questionable" / "final" / subject
            (raw / "Myelin").mkdir(parents=True)
            output.mkdir(parents=True)
            input_dir.mkdir(parents=True)
            raw_data = np.zeros((8, 10, 7), dtype=np.float32)
            raw_data[0, 0, 0] = 0.003
            raw_data[2:5, 3:7, 1:4] = 2
            denoised = np.zeros((6, 7, 5), dtype=np.float32)
            denoised[1:4, 1:5, 1:4] = 9
            nib.Nifti1Image(raw_data, np.eye(4)).to_filename(raw / "T1_acpc.nii.gz")
            nib.Nifti1Image(denoised, np.eye(4)).to_filename(output / "T1_age.nii.gz")
            (input_dir / "resize_meta.json").write_text(
                json.dumps({
                    "raw_shape": [8, 10, 7],
                    "target_shape": [6, 7, 5],
                    "bbox_start": [2, 3, 1],
                    "bbox_stop": [5, 7, 4],
                    "target_offset": [1, 1, 1],
                    "resize_threshold": 0.0,
                }),
                encoding="utf-8",
            )
            (raw / "T2_acpc.nii.gz").write_bytes(b"t2")
            (raw / "mask.nii.gz").write_bytes(b"mask")
            (raw / "Myelin" / "myelin.txt").write_bytes(b"myelin")
            rows = [{
                "subject_name": subject,
                "status": "pending",
                "output_path": str(output / "T1_age.nii.gz"),
                "final_path": str(final / "T1_acpc.nii.gz"),
                "runtime_seconds": "",
                "error": "",
            }]
            mod.collect_outputs(rows, batch, runtime_seconds=1.0, model_failed=False)
            final_t1 = nib.load(final / "T1_acpc.nii.gz").get_fdata()
            self.assertEqual(final_t1.shape, (8, 10, 7))
            self.assertAlmostEqual(float(final_t1[0, 0, 0]), 0.003, places=6)
            self.assertEqual(float(final_t1[2, 3, 1]), 9.0)
            self.assertEqual((final / "T2_acpc.nii.gz").read_bytes(), b"t2")
            self.assertEqual((final / "mask.nii.gz").read_bytes(), b"mask")
            self.assertEqual((final / "Myelin" / "myelin.txt").read_bytes(), b"myelin")

    def test_moardiff_can_collect_existing_output_without_input_dir(self):
        import nibabel as nib
        import numpy as np

        mod = load_script("21_run_moardiff_denoise_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            subject = "0101010268_67mo"
            raw = batch / "5_questionable" / "raw" / subject
            output = batch / "5_questionable" / "output" / subject
            raw.mkdir(parents=True)
            output.mkdir(parents=True)
            raw_data = np.zeros((8, 10, 7), dtype=np.float32)
            raw_data[2:5, 3:7, 1:4] = 2
            denoised = np.zeros((192, 240, 192), dtype=np.float32)
            denoised[94:97, 118:122, 94:97] = 9
            nib.Nifti1Image(raw_data, np.eye(4)).to_filename(raw / "T1_acpc.nii.gz")
            nib.Nifti1Image(denoised, np.eye(4)).to_filename(output / "T1_age.nii.gz")
            names = mod.discover_subject_names(
                batch / "5_questionable" / "input",
                batch / "5_questionable" / "output",
                batch / "5_questionable" / "raw",
            )
            self.assertEqual(names, [subject])
            row = mod.row_for(subject, batch / "5_questionable" / "input", batch, Path("ckpt.pth"), Path("model"))
            self.assertEqual(row["status"], "pending_collect")
            mod.collect_outputs([row], batch, runtime_seconds=0.0, collect_statuses={"pending_collect"})
            self.assertEqual(row["status"], "success")
            self.assertEqual(nib.load(row["final_path"]).shape, (8, 10, 7))

    def test_report_writer_handles_missing_manifests(self):
        mod = load_script("11_write_preprocessing_report_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            (batch / "manifests").mkdir()
            report = mod.build_report(batch)
            text = report.read_text(encoding="utf-8")
        self.assertIn("sMRI preprocessing report", text)
        self.assertIn("00 Age suffix", text)

    def test_recon_checker_accepts_questionable_presurf_root(self):
        mod = load_script("31_check_recon_outputs_v2.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "5_questionable" / "presurf"
            subj = root / "0101010268_67mo"
            subj.mkdir(parents=True)
            (subj / "masked.nii.gz").write_bytes(b"masked")
            (subj / "aseg.nii.gz").write_bytes(b"aseg")
            rows = mod.collect(root)
            self.assertEqual(rows[0]["subject_name"], "0101010268_67mo")
            self.assertEqual(rows[0]["status"], "pending")


    def test_recon_checker_marks_fatal_recon_log_as_failed(self):
        mod = load_script("31_check_recon_outputs_v2.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "7_presurf"
            subj = root / "0101010265_13mo"
            (subj / "mri").mkdir(parents=True)
            (subj / "log").mkdir()
            (subj / "masked.nii.gz").write_bytes(b"masked")
            (subj / "aseg.nii.gz").write_bytes(b"aseg")
            (subj / "mri" / "aseg.mgz").write_bytes(b"partial")
            (subj / "log" / "recon.log").write_text(
                "reg_aladin: error while loading shared libraries: libpng16.so.16\nERROR | Fatal\n",
                encoding="utf-8",
            )
            rows = mod.collect(root)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertIn("recon log indicates failure", rows[0]["error"])

    def test_postprocessing_report_can_write_questionable_report_path(self):
        mod = load_script("32_write_postprocessing_report_v2.py")
        with tempfile.TemporaryDirectory() as td:
            batch = Path(td)
            manifest = batch / "manifests"
            manifest.mkdir()
            (manifest / "30_questionable_presurf_summary.csv").write_text(
                "subject_name,status,error\n0101010268_67mo,success,\n",
                encoding="utf-8",
            )
            report_path = batch / "5_questionable" / "logs" / "questionable_postprocessing_report.md"
            out = mod.build_report(batch, report_path=report_path)
            text = out.read_text(encoding="utf-8")
            self.assertIn("30 questionable presurf", text)
            self.assertTrue(str(out).endswith("questionable_postprocessing_report.md"))


if __name__ == "__main__":
    unittest.main()



