import sys
import time

from ctk_builder.runner import ProcessRunner
from ctk_builder.settings import Settings


def collect(runner: ProcessRunner, until: str, timeout: float = 10.0) -> str:
    text = ""
    deadline = time.monotonic() + timeout
    while until not in text and time.monotonic() < deadline:
        text += runner.drain()
        time.sleep(0.05)
    return text


def test_runner_captures_output_and_exit_code(tmp_path):
    script = tmp_path / "hallo.py"
    script.write_text("import sys\nprint('hallo')\nsys.exit(3)\n", encoding="utf-8")
    runner = ProcessRunner()
    runner.start(sys.executable, script)
    text = collect(runner, "beendet")
    assert "hallo" in text
    assert "Code 3" in text
    assert not runner.running


def test_runner_stop(tmp_path):
    script = tmp_path / "endlos.py"
    script.write_text("import time\nprint('start', flush=True)\ntime.sleep(60)\n",
                      encoding="utf-8")
    runner = ProcessRunner()
    runner.start(sys.executable, script)
    collect(runner, "start")
    assert runner.running
    runner.stop()
    assert not runner.running


def test_settings_default_and_persist(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(path)
    assert settings.interpreter == sys.executable
    settings.interpreter = "/usr/bin/python3"
    assert Settings(path).interpreter == "/usr/bin/python3"


def test_settings_broken_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("kaputt", encoding="utf-8")
    assert Settings(path).interpreter == sys.executable
