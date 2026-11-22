"""Regression tests for the electrical evidence reported in PR #177."""
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

ELEC = Path(__file__).resolve().parent
CLASSIFIER = runpy.run_path(str(ELEC / "classify.py"))
BEGIN = "===KLT_STA_MAX_SLEW_BEGIN==="
END = "===KLT_STA_MAX_SLEW_END==="
OK = "KLT_ELECTRICAL_OK"
CAP = f"===KLT_STA_MAX_CAP_BEGIN===\n{OK}\n===KLT_STA_MAX_CAP_END==="
ROW = "u2/A 1.50000 1.70000 -0.20000 (VIOLATED)"
MAP = "KLT_ELECTRICAL_NET u2/A net1"


class ElectricalEvidence(unittest.TestCase):
    def test_incomplete_checks(self):
        empty = f"{BEGIN}\n{OK}\n{END}\n"
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "corner.log"
            log.write_text(empty + CAP)
            reports, _ = CLASSIFIER["parse_log"](log)
            self.assertEqual(reports["max_capacitance"], {"coverage": "checked", "rows": []})
            for content in (empty, empty + CAP.replace(OK, "KLT_ELECTRICAL_UNSUPPORTED"),
                            empty + empty + CAP):
                with self.subTest(content=content), self.assertRaises(SystemExit):
                    log.write_text(content)
                    CLASSIFIER["parse_log"](log)

    def test_rows_and_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "corner.log"
            for body in ("u2/A broken (VIOLATED)\n" + MAP, ROW, MAP,
                         ROW + "\n" + MAP.replace("u2/A", "u3/A"),
                         "\n".join((ROW, MAP, MAP)), "\n".join((ROW, ROW, MAP))):
                with self.subTest(body=body), self.assertRaises(SystemExit):
                    log.write_text("\n".join((BEGIN, body, OK, END, CAP)))
                    CLASSIFIER["parse_log"](log)
            # A recoverable column from baseline corner ss_n40C_1v76.
            row = "u2/A 1.50000 1.912600 1.91268 -0.41268 (VIOLATED)"
            log.write_text("\n".join((BEGIN, row, MAP, OK, END, CAP)))
            reports, _ = CLASSIFIER["parse_log"](log)
            self.assertEqual(reports["max_transition"]["rows"][0]["value"], 1.91268)

    def test_synthesized_hierarchy(self):
        cells = CLASSIFIER["netlist_instances"](CLASSIFIER["NETLIST"], "hyperram_ctrl")
        self.assertEqual(cells["u_cap/_630_"], "sky130_fd_sc_hd__and3_1")
        self.assertIn("u_out/u_ck_dly/g_dly[0].u_dly", cells)
        self.assertIn("u_cap/u_rwds_dly/g_dly[0].u_dly", cells)
        self.assertNotIn("u_fsm/fanout4", cells)

    def test_geometry_is_bound_before_render(self):
        root = ELEC.parents[1]
        binding = json.loads((ELEC / "records/sta-inputs.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            electrical = copy / "layout/electrical"
            shutil.copytree(ELEC / "records", electrical / "records")
            for name in ("classify.py", "sta-request.json"):
                shutil.copy2(ELEC / name, electrical / name)
            paths = [entry["path"] for entry in binding["geometry"].values()]
            for rel in paths + ["layout/records/place-and-route.response.json",
                                str(CLASSIFIER["NETLIST"].relative_to(root))]:
                (copy / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, copy / rel)
            cmd = [sys.executable, "-I", str(electrical / "classify.py")]
            subprocess.run([*cmd, "--check"], check=True, stdout=subprocess.PIPE)
            for rel in paths:
                path = copy / rel
                with path.open("ab") as altered:
                    altered.write(b"\n")
                for args in ([], ["--check"]):
                    with self.subTest(path=rel, args=args):
                        result = subprocess.run(cmd + args, capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertRegex(result.stderr, "measured DEF|changed since measurement")
                shutil.copy2(root / rel, path)


if __name__ == "__main__":
    unittest.main()
