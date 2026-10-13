import pytest

from ctk_builder.codegen import HEADER
from ctk_builder.exporter import ExportNeedsConfirmation, export, module_name_for


@pytest.mark.parametrize("filename,expected", [
    ("kontakt.ctkb.json", "kontakt"),
    ("Mein Fenster.ctkb.json", "mein_fenster"),
    ("2fa.ctkb.json", "app_2fa"),
    ("class.ctkb.json", "app_class"),
    ("x.json", "x"),
])
def test_module_name_for(filename, expected):
    assert module_name_for(filename) == expected


def test_first_export_creates_both_files(tmp_path, kontakt):
    result = export(kontakt, tmp_path / "kontakt.ctkb.json")
    assert result.ui_path == tmp_path / "kontakt_ui.py"
    assert result.logic_path == tmp_path / "kontakt.py"
    assert result.logic_created
    assert result.ui_path.read_text(encoding="utf-8").startswith(HEADER)


def test_second_export_keeps_logic_file(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    export(kontakt, path)
    (tmp_path / "kontakt.py").write_text("# meine Logik\n", encoding="utf-8")
    kontakt.window.title = "Geändert"
    result = export(kontakt, path)
    assert not result.logic_created
    assert (tmp_path / "kontakt.py").read_text(encoding="utf-8") == "# meine Logik\n"
    assert '"Geändert"' in (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8")


def test_hand_edited_ui_file_needs_confirmation(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    (tmp_path / "kontakt_ui.py").write_text("# von Hand\n", encoding="utf-8")
    with pytest.raises(ExportNeedsConfirmation):
        export(kontakt, path)
    assert (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8") == "# von Hand\n"
    export(kontakt, path, force=True)
    assert (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8").startswith(HEADER)
