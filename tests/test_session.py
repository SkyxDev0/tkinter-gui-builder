import pytest

from conftest import build_kontakt
from ctk_builder.commands import AddWidget, RemoveWidget
from ctk_builder.project_io import ProjectFileError
from ctk_builder.session import Session


@pytest.fixture
def session():
    return Session()


def test_execute_success_and_failure(session):
    messages = []
    session.on_status = messages.append
    assert session.execute(AddWidget("window", "CTkLabel", 0, 0))
    assert not session.execute(AddWidget("window", "CTkLabel", 0, 0))
    assert messages == ["Zelle ist schon belegt"]


def test_model_listeners_called(session):
    calls = []
    session.subscribe(lambda: calls.append("model"))
    session.subscribe_selection(lambda: calls.append("selection"))
    session.execute(AddWidget("window", "CTkLabel"))
    assert calls == ["model"]
    session.select("window")
    assert calls == ["model", "selection"]


def test_selection_resets_when_node_disappears(session):
    command = AddWidget("window", "CTkLabel")
    session.execute(command)
    session.select(command.node_id)
    calls = []
    session.subscribe_selection(lambda: calls.append(1))
    session.execute(RemoveWidget(command.node_id))
    assert session.selected_id == "window"
    assert calls == [1]


def test_line_selection(session):
    session.select_line("window", "column", 0)
    assert session.selected_id == "window"
    assert session.selected_line == ("window", "column", 0)
    session.select("window")
    assert session.selected_line is None


def test_target_container(session):
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    label = AddWidget(frame.node_id, "CTkLabel")
    session.execute(label)
    assert session.target_container_id() == "window"
    session.select(frame.node_id)
    assert session.target_container_id() == frame.node_id
    session.select(label.node_id)
    assert session.target_container_id() == frame.node_id


def test_save_open_new(tmp_path, session):
    session.replace_project(build_kontakt(), None)
    assert not session.dirty
    session.execute(AddWidget("window", "CTkLabel"))
    assert session.dirty
    with pytest.raises(ValueError):
        session.save()
    path = tmp_path / "k.ctkb.json"
    session.save(path)
    assert not session.dirty
    assert session.path == path

    calls = []
    session.subscribe(lambda: calls.append(1))
    session.new()
    assert session.path is None
    assert session.project.window.children == []
    session.open(path)
    assert session.path == path
    assert len(list(session.project.iter_widgets())) == 10
    assert len(calls) == 2
    # Nach dem Öffnen hängen Beobachter am neuen Projekt
    session.execute(AddWidget("window", "CTkLabel"))
    assert len(calls) == 3


def test_open_broken_file_keeps_project(tmp_path, session):
    path = tmp_path / "kaputt.ctkb.json"
    path.write_text("{", encoding="utf-8")
    session.execute(AddWidget("window", "CTkLabel"))
    with pytest.raises(ProjectFileError):
        session.open(path)
    assert len(list(session.project.iter_widgets())) == 1
