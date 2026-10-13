import os
import subprocess
import sys
from pathlib import Path

import pytest

from ctk_builder import __version__, runner
from ctk_builder.cli import RUN_SCRIPT_FLAG, main


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_run_script_executes_as_main(tmp_path, monkeypatch):
    (tmp_path / "helfer.py").write_text("WERT = 'aus Nachbarmodul'\n", encoding="utf-8")
    script = tmp_path / "programm.py"
    script.write_text(
        "from pathlib import Path\n"
        "import helfer\n"
        "if __name__ == '__main__':\n"
        "    Path('ergebnis.txt').write_text(helfer.WERT, encoding='utf-8')\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    main([RUN_SCRIPT_FLAG, str(script)])
    assert (tmp_path / "ergebnis.txt").read_text(encoding="utf-8") == "aus Nachbarmodul"


def test_run_script_as_subprocess_prints_output(tmp_path):
    script = tmp_path / "hallo.py"
    script.write_text("print('Grüße')\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "ctk_builder", RUN_SCRIPT_FLAG, script.name],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent),
             "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Grüße\n"


def test_script_command(monkeypatch):
    script = Path("/tmp/kontakt.py")
    assert runner.script_command("/usr/bin/python3", script) == ["/usr/bin/python3", "-u", "kontakt.py"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Apps/CTk Builder")
    assert runner.script_command("/Apps/CTk Builder", script) == [
        "/Apps/CTk Builder", RUN_SCRIPT_FLAG, "kontakt.py"]
    # ein ausdrücklich gewählter Interpreter wird normal benutzt
    assert runner.script_command("/usr/bin/python3", script)[1] == "-u"
