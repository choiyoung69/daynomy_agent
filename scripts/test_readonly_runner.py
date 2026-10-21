#!/usr/bin/env python3
"""Real native-process probes of the read-only Cargo runner, no model calls."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).with_name("readonly_runner.py")


class ReadOnlyRunnerTests(unittest.TestCase):
    def test_nonwriting_native_process_succeeds(self):
        result = subprocess.run([sys.executable, str(RUNNER), "/usr/bin/true"],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, "Read-only runtime could not execute native program")

    def test_native_write_attempt_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="daynomy-readonly-") as temporary:
            directory = Path(temporary)
            sentinel = directory / "trusted-criteria.txt"
            sentinel.write_text("criteria must remain unchanged")
            source, binary = directory / "probe.c", directory / "probe"
            source.write_text('''#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc != 2) return 20;
    int fd = open(argv[1], O_WRONLY | O_TRUNC);
    if (fd >= 0) { close(fd); return 21; }
    return errno == EPERM || errno == EACCES ? 0 : 22;
}
''')
            compile_result = subprocess.run(["/usr/bin/cc", str(source), "-o", str(binary)],
                                            capture_output=True, timeout=60)
            self.assertEqual(compile_result.returncode, 0, "Native probe compilation failed")
            # Without the runner the same probe can truncate this writable file.
            unsandboxed = subprocess.run([str(binary), str(sentinel)], capture_output=True, timeout=10)
            self.assertEqual(unsandboxed.returncode, 21)
            sentinel.write_text("criteria must remain unchanged")
            sandboxed = subprocess.run([sys.executable, str(RUNNER), str(binary), str(sentinel)],
                                       capture_output=True, timeout=30)
            self.assertEqual(sandboxed.returncode, 0, "Native write was not denied by sandbox")
            self.assertEqual(sentinel.read_text(), "criteria must remain unchanged")


if __name__ == "__main__":
    unittest.main()
