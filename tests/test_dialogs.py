"""Datei-Dialoge: Absturzschutz unter macOS, Dateinamen, Überschreiben, Fehler."""

from pathlib import Path

import pytest

from conftest import requires_display
from ctk_builder.commands import SetWindowProperty
from ctk_builder.project_io import SUFFIX
from ctk_builder.session import Session
from ctk_builder.settings import Settings
from ctk_builder.ui import main_window
from ctk_builder.ui.main_window import (
    FILETYPES, MainWindow, needs_overwrite_prompt, project_dialog_options, project_path,
)


def tk_extensions(options):
    """Endungen, wie Tk unter macOS sie an [UTType typeWithFilenameExtension:] gibt.

    tkMacOSXDialog.c entfernt nur führende „*“ und „.“ (Muster und defaultextension).
    """
    patterns = [p for _, group in options.get("filetypes", []) for p in group.split()]
    if "defaultextension" in options:
        patterns.append(options["defaultextension"])
    return [p.lstrip("*.") for p in patterns]


@pytest.mark.parametrize("save", [True, False])
def test_macos_dialog_has_no_dotted_extension(save):
    """Regression: „ctkb.json“ ergibt unter macOS einen nil-UTType -> Absturz."""
    options = project_dialog_options(save=save, initialfile="app.ctkb.json", platform="darwin")
    extensions = tk_extensions(options)
    assert extensions == ["json"]
    assert all("." not in ext for ext in extensions)


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_other_platforms_keep_project_filter(platform):
    assert project_dialog_options(save=True, initialfile="a.ctkb.json", platform=platform) == {
        "filetypes": FILETYPES, "defaultextension": SUFFIX, "initialfile": "a.ctkb.json"}
    assert project_dialog_options(save=False, initialfile="a.ctkb.json", platform=platform) == {
        "filetypes": FILETYPES}


@pytest.mark.parametrize("chosen,expected", [
    ("kontakt", "kontakt.ctkb.json"),
    ("kontakt.json", "kontakt.ctkb.json"),
    ("kontakt.ctkb", "kontakt.ctkb.json"),
    ("kontakt.ctkb.json", "kontakt.ctkb.json"),
    ("Kontakt.CTKB.JSON", "Kontakt.ctkb.json"),
    ("Kontakt.JSON", "Kontakt.ctkb.json"),
    ("kontakt.txt", "kontakt.txt.ctkb.json"),
    ("kontakt.txt.json", "kontakt.txt.ctkb.json"),
])
def test_project_path(chosen, expected):
    assert project_path(f"/ordner/{chosen}") == Path("/ordner") / expected


def test_needs_overwrite_prompt(tmp_path):
    final = tmp_path / "kontakt.ctkb.json"
    assert not needs_overwrite_prompt(str(tmp_path / "kontakt.json"), final)  # gibt es nicht
    final.write_text("{}", encoding="utf-8")
    # Dialog hat nach kontakt.json gefragt, geschrieben würde kontakt.ctkb.json
    assert needs_overwrite_prompt(str(tmp_path / "kontakt.json"), final)
    # Dialog hat genau nach dieser Datei gefragt
    assert not needs_overwrite_prompt(str(final), final)


def test_overwrite_prompt_on_drives_without_file_ids(tmp_path, monkeypatch):
    """Manche Netz-/Cloud-Laufwerke geben jeder Datei st_ino 0 – samefile() irrt dort."""
    (tmp_path / "kontakt.json").write_text("{}", encoding="utf-8")
    final = tmp_path / "kontakt.ctkb.json"
    final.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main_window.os.path, "samefile", lambda a, b: True)
    assert needs_overwrite_prompt(str(tmp_path / "kontakt.json"), final)
    assert not needs_overwrite_prompt(str(final), final)


def test_session_keeps_path_when_saving_fails(tmp_path):
    session = Session()
    with pytest.raises(OSError):
        session.save(tmp_path / "fehlt" / "x.ctkb.json")
    assert session.path is None


# ---------------------------------------------------------------- im Hauptfenster

class FakeDialog:
    """Ersetzt einen tkinter-Dateidialog und merkt sich die Aufrufe."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return str(self.answer)


def test_save_as_on_macos(app, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window, "PLATFORM", "darwin")
    dialog = FakeDialog(tmp_path / "kontakt.json")  # so liefert das macOS-Panel „kontakt“
    monkeypatch.setattr(main_window.filedialog, "asksaveasfilename", dialog)
    assert app.save_as()
    options = dialog.calls[0]
    assert options["filetypes"] == main_window.MAC_FILETYPES
    assert "defaultextension" not in options
    assert options["initialfile"] == "kontakt.ctkb.json"
    assert app.session.path == tmp_path / "kontakt.ctkb.json"
    assert app.session.path.exists()
    assert not app.session.dirty


@pytest.mark.parametrize("replace", [False, True])
def test_save_as_asks_before_overwriting_other_name(app, tmp_path, monkeypatch, replace):
    existing = tmp_path / "kontakt.ctkb.json"
    existing.write_text("alt", encoding="utf-8")
    monkeypatch.setattr(main_window.filedialog, "asksaveasfilename",
                        FakeDialog(tmp_path / "kontakt.json"))
    questions = []
    monkeypatch.setattr(main_window.messagebox, "askyesno",
                        lambda *args, **kwargs: questions.append(args) or replace)
    assert app.save_as() is replace
    assert len(questions) == 1 and "kontakt.ctkb.json" in questions[0][1]
    assert (existing.read_text(encoding="utf-8") == "alt") is not replace
    assert app.session.path == (existing if replace else None)


def test_save_error_is_reported_and_path_kept(app, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window.filedialog, "asksaveasfilename",
                        FakeDialog(tmp_path / "fehlt" / "kontakt.ctkb.json"))
    errors = []
    monkeypatch.setattr(main_window.messagebox, "showerror",
                        lambda *args, **kwargs: errors.append(args))
    assert not app.save_as()
    assert errors and errors[0][0] == "Speichern fehlgeschlagen"
    assert app.session.path is None
    assert app.export() is None  # Export bricht ohne Speicherort sauber ab


def test_open_on_macos_uses_simple_extension(app, tmp_path, monkeypatch):
    path = tmp_path / "kontakt.ctkb.json"
    app.session.save(path)
    monkeypatch.setattr(main_window, "PLATFORM", "darwin")
    dialog = FakeDialog(path)
    monkeypatch.setattr(main_window.filedialog, "askopenfilename", dialog)
    app.open_project()
    assert dialog.calls[0] == {"parent": app, "filetypes": main_window.MAC_FILETYPES}
    assert app.session.path == path


def test_no_second_dialog_while_one_is_open(app, tmp_path, monkeypatch):
    inner = []

    def dialog(**kwargs):
        inner.append(app.save_as())  # z. B. Menü „Speichern unter…“ während des Dialogs
        return ""

    monkeypatch.setattr(main_window.filedialog, "asksaveasfilename", dialog)
    assert not app.save_as()
    assert inner == [False]


@pytest.mark.parametrize("action", ["new_project", "open_project", "quit_app"])
def test_no_new_open_or_quit_while_save_dialog_is_open(app, tmp_path, monkeypatch, action):
    """Menüs bleiben unter macOS im Dialog bedienbar; „Neu“ darf das Projekt nicht tauschen."""
    app.session.execute(SetWindowProperty("title", "Meine Arbeit"))  # ungespeichert
    project = app.session.project
    asked = []
    monkeypatch.setattr(main_window.messagebox, "askyesnocancel",
                        lambda *args, **kwargs: asked.append(args) or False)
    monkeypatch.setattr(main_window.filedialog, "askopenfilename", FakeDialog(""))

    def dialog(**kwargs):
        getattr(app, action)()  # Menü „Neu“/„Öffnen“/„Beenden“ während des Dialogs
        return str(tmp_path / "kontakt.json")

    monkeypatch.setattr(main_window.filedialog, "asksaveasfilename", dialog)
    assert app.save_as()
    assert asked == []
    assert app.session.project is project
    assert app.winfo_exists()
    saved = Session()
    saved.open(tmp_path / "kontakt.ctkb.json")
    assert saved.project.window.title == "Meine Arbeit"


@requires_display
def test_mac_quit_goes_through_quit_app(tmp_path, monkeypatch):
    """Cmd+Q ruft ::tk::mac::Quit – das muss nachfragen statt sofort zu beenden."""
    monkeypatch.setattr(main_window, "PLATFORM", "darwin")
    calls = []
    monkeypatch.setattr(MainWindow, "quit_app", lambda self: calls.append(self))
    window = MainWindow(Session(), Settings(tmp_path / "settings.json"))
    try:
        window.tk.call("::tk::mac::Quit")
        assert calls == [window]
    finally:
        window.destroy()
