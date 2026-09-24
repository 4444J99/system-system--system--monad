import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

BIN_SYS_LOG_EVENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "sys-log-event"))

class TestSysLogEventPaths(unittest.TestCase):

    def run_cli(self, args, env, cwd=None):
        cmd = [sys.executable, BIN_SYS_LOG_EVENT] + args
        return subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

    def test_bare_relative_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ, SYS_LEDGER_PATH="ledger.jsonl")
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1", "--payload", '{"key": "val"}'],
                env=env,
                cwd=tmpdir
            )
            self.assertEqual(res.returncode, 0, f"Stderr: {res.stderr}")
            expected_file = os.path.join(tmpdir, "ledger.jsonl")
            self.assertTrue(os.path.isfile(expected_file))
            with open(expected_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event_type"], "TEST_EVENT")

    def test_nested_relative_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ, SYS_LEDGER_PATH="nested/dir/ledger.jsonl")
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1", "--payload", '{"key": "val"}'],
                env=env,
                cwd=tmpdir
            )
            self.assertEqual(res.returncode, 0, f"Stderr: {res.stderr}")
            expected_file = os.path.join(tmpdir, "nested", "dir", "ledger.jsonl")
            self.assertTrue(os.path.isfile(expected_file))
            with open(expected_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)

    def test_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_ledger = os.path.join(tmpdir, "abs_ledger.jsonl")
            env = dict(os.environ, SYS_LEDGER_PATH=abs_ledger)
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1", "--payload", '{"key": "val"}'],
                env=env
            )
            self.assertEqual(res.returncode, 0, f"Stderr: {res.stderr}")
            self.assertTrue(os.path.isfile(abs_ledger))

    def test_unicode_and_spaces_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "path with spaces", "🔥_ledger.jsonl")
            env = dict(os.environ, SYS_LEDGER_PATH=ledger_path)
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1", "--payload", '{"emoji": "🔥"}'],
                env=env
            )
            self.assertEqual(res.returncode, 0, f"Stderr: {res.stderr}")
            self.assertTrue(os.path.isfile(ledger_path))
            with open(ledger_path, "r", encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertEqual(record["payload"]["emoji"], "🔥")

    def test_sequential_appends_preserve_prior_bytes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "ledger.jsonl")
            env = dict(os.environ, SYS_LEDGER_PATH=ledger_path)

            res1 = self.run_cli(
                ["--type", "EVENT_1", "--targets", "UID_1"],
                env=env
            )
            self.assertEqual(res1.returncode, 0)

            with open(ledger_path, "r", encoding="utf-8") as f:
                first_content = f.read()

            res2 = self.run_cli(
                ["--type", "EVENT_2", "--targets", "UID_2"],
                env=env
            )
            self.assertEqual(res2.returncode, 0)

            with open(ledger_path, "r", encoding="utf-8") as f:
                full_content = f.read()

            self.assertTrue(full_content.startswith(first_content))
            lines = [line for line in full_content.splitlines() if line]
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event_type"], "EVENT_1")
            self.assertEqual(json.loads(lines[1])["event_type"], "EVENT_2")

    def test_malformed_payload_causes_no_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "ledger.jsonl")
            env = dict(os.environ, SYS_LEDGER_PATH=ledger_path)
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1", "--payload", 'invalid json{'],
                env=env
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertFalse(os.path.exists(ledger_path))

    def test_directory_destination_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ, SYS_LEDGER_PATH=tmpdir)
            res = self.run_cli(
                ["--type", "TEST_EVENT", "--targets", "UID_1"],
                env=env
            )
            self.assertNotEqual(res.returncode, 0)

    def test_unwritable_destination_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            read_only_dir = os.path.join(tmpdir, "readonly")
            os.makedirs(read_only_dir)
            os.chmod(read_only_dir, stat.S_IRUSR | stat.S_IXUSR)

            ledger_path = os.path.join(read_only_dir, "ledger.jsonl")
            env = dict(os.environ, SYS_LEDGER_PATH=ledger_path)

            try:
                res = self.run_cli(
                    ["--type", "TEST_EVENT", "--targets", "UID_1"],
                    env=env
                )
                self.assertNotEqual(res.returncode, 0)
            finally:
                os.chmod(read_only_dir, stat.S_IRWXU)

if __name__ == "__main__":
    unittest.main()
