import copy

import pytest

from conftest import grid_project
from ctk_builder.commands import (
    AddWidget, CommandError, CommandStack, DuplicateWidget, InsertLine, MoveWidget,
    RemoveLine, RemoveWidget, RenameWidget, SetLayout, SetLineConfig, SetProperty,
    SetWindowProperty,
)
from ctk_builder.model import LineConfig


@pytest.fixture
def stack():
    return CommandStack(grid_project())


def add(stack, widget_type="CTkLabel", parent="window", row=None, column=None):
    cmd = AddWidget(parent, widget_type, row, column)
    stack.execute(cmd)
    return stack.project.find(cmd.node_id)


def snapshot(stack):
    return copy.deepcopy(stack.project.window)


def assert_undo_restores(stack, command):
    """Führt command aus, macht es rückgängig, prüft Gleichheit, macht Redo."""
    before = snapshot(stack)
    stack.execute(command)
    after = snapshot(stack)
    stack.undo()
    assert stack.project.window == before
    stack.redo()
    assert stack.project.window == after


def test_add_widget_uses_initial_props_and_unique_name(stack):
    label = add(stack)
    assert label.name == "label_1"
    assert label.props == {"text": "Label"}
    assert (label.layout.row, label.layout.column) == (0, 0)
    assert add(stack).name == "label_2"


def test_add_widget_without_cell_takes_next_free_and_grows(stack):
    add(stack)
    second = add(stack)
    assert (second.layout.row, second.layout.column) == (1, 0)
    assert len(stack.project.window.grid.rows) == 2


def test_add_on_edge_appends_column(stack):
    add(stack, row=0, column=0)
    add(stack, row=0, column=1)
    assert len(stack.project.window.grid.columns) == 2


def test_add_rejects_occupied_and_far_away_cells(stack):
    add(stack, row=0, column=0)
    before = snapshot(stack)
    with pytest.raises(CommandError):
        stack.execute(AddWidget("window", "CTkLabel", 0, 0))
    with pytest.raises(CommandError):
        stack.execute(AddWidget("window", "CTkLabel", 5, 0))
    assert stack.project.window == before
    assert not stack.can_redo


def test_add_frame_creates_grid_and_children_go_inside(stack):
    frame = add(stack, "CTkFrame")
    assert frame.grid is not None
    button = add(stack, "CTkButton", parent=frame.id)
    assert stack.project.parent_of(button.id).id == frame.id


def test_add_into_non_container_fails(stack):
    label = add(stack)
    with pytest.raises(CommandError):
        stack.execute(AddWidget(label.id, "CTkLabel"))


def test_add_undo_redo(stack):
    assert_undo_restores(stack, AddWidget("window", "CTkButton", 0, 0))


def test_redo_keeps_node_id(stack):
    cmd = AddWidget("window", "CTkButton", 0, 0)
    stack.execute(cmd)
    stack.undo()
    stack.redo()
    assert stack.project.find(cmd.node_id) is not None


def test_remove_widget(stack):
    label = add(stack)
    assert_undo_restores(stack, RemoveWidget(label.id))
    assert stack.project.find(label.id) is None


def test_move_to_empty_cell(stack):
    label = add(stack, row=0, column=0)
    assert_undo_restores(stack, MoveWidget(label.id, "window", 0, 1))
    moved = stack.project.find(label.id)
    assert (moved.layout.row, moved.layout.column) == (0, 1)


def test_move_onto_occupied_cell_swaps(stack):
    a = add(stack, row=0, column=0)
    b = add(stack, row=0, column=1)
    stack.execute(MoveWidget(a.id, "window", 0, 1))
    a, b = stack.project.find(a.id), stack.project.find(b.id)
    assert (a.layout.row, a.layout.column) == (0, 1)
    assert (b.layout.row, b.layout.column) == (0, 0)


def test_move_into_and_out_of_frame(stack):
    frame = add(stack, "CTkFrame", row=0, column=0)
    label = add(stack, row=1, column=0)
    stack.execute(MoveWidget(label.id, frame.id, 0, 0))
    assert stack.project.parent_of(label.id).id == frame.id
    stack.execute(MoveWidget(label.id, "window", 1, 0))
    assert stack.project.parent_of(label.id).id == "window"


def test_move_frame_into_itself_fails(stack):
    outer = add(stack, "CTkFrame")
    inner = add(stack, "CTkFrame", parent=outer.id)
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(outer.id, outer.id, 0, 0))
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(outer.id, inner.id, 0, 0))


def test_swap_with_spanning_widget_that_does_not_fit_fails(stack):
    a = add(stack, row=0, column=0)
    b = add(stack, row=0, column=1)
    add(stack, row=1, column=0)
    stack.execute(SetLayout(b.id, rowspan=2))  # b belegt (0,1) und (1,1)
    before = snapshot(stack)
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(a.id, "window", 0, 1))  # b müsste nach (0,0) mit rowspan 2
    assert stack.project.window == before


def test_duplicate_widget_copies_subtree_with_new_names(stack):
    frame = add(stack, "CTkFrame")
    add(stack, "CTkButton", parent=frame.id)
    cmd = DuplicateWidget(frame.id)
    stack.execute(cmd)
    clone = stack.project.find(cmd.new_node_id)
    assert clone.name == "frame_2"
    assert clone.children[0].name == "button_2"
    assert clone.id != frame.id
    assert clone.children[0].id != frame.children[0].id
    assert (clone.layout.row, clone.layout.column) == (1, 0)
    names = [w.name for w in stack.project.iter_widgets()]
    assert len(names) == len(set(names))


def test_rename(stack):
    label = add(stack)
    add(stack)
    stack.execute(RenameWidget(label.id, "label_title"))
    assert stack.project.find(label.id).name == "label_title"
    with pytest.raises(CommandError):
        stack.execute(RenameWidget(label.id, "label_2"))
    with pytest.raises(CommandError):
        stack.execute(RenameWidget(label.id, "class"))


def test_set_property_and_reset_to_default(stack):
    button = add(stack, "CTkButton")
    assert_undo_restores(stack, SetProperty(button.id, "text", "Speichern"))
    stack.execute(SetProperty(button.id, "command", "on_save"))
    assert stack.project.find(button.id).props["command"] == "on_save"
    stack.execute(SetProperty(button.id, "command", None))
    assert "command" not in stack.project.find(button.id).props


def test_set_property_checks_handler_names(stack):
    button = add(stack, "CTkButton")
    with pytest.raises(CommandError):
        stack.execute(SetProperty(button.id, "command", button.name))
    with pytest.raises(KeyError):
        stack.execute(SetProperty(button.id, "gibtsnicht", 1))


def test_set_layout(stack):
    label = add(stack, row=0, column=0)
    add(stack, row=0, column=1)
    stack.execute(SetLayout(label.id, sticky="wens", padx=4))
    assert stack.project.find(label.id).layout.sticky == "nsew"
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, columnspan=2))  # überdeckt Nachbarn
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, sticky="x"))
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, padx=-1))
    with pytest.raises(ValueError):
        SetLayout(label.id, farbe="rot")


def test_set_window_property(stack):
    assert_undo_restores(stack, SetWindowProperty("title", "Kontakt"))
    stack.execute(SetWindowProperty("width", 640))
    assert stack.project.window.width == 640
    for key, value in [("width", 0), ("class_name", "1x"),
                       ("appearance_mode", "pink"), ("color_theme", "red")]:
        with pytest.raises(CommandError):
            stack.execute(SetWindowProperty(key, value))


def test_insert_line_shifts_and_extends_spans(stack):
    a = add(stack, row=0, column=0)
    stack.execute(InsertLine("window", "row", 1))
    stack.execute(SetLayout(a.id, rowspan=2))  # a belegt Zeilen 0 und 1
    b = add(stack, row=2, column=0)
    assert_undo_restores(stack, InsertLine("window", "row", 1))
    a, b = stack.project.find(a.id), stack.project.find(b.id)
    assert a.layout.rowspan == 3
    assert b.layout.row == 3
    assert len(stack.project.window.grid.rows) == 4


def test_remove_line(stack):
    add(stack, row=0, column=0)
    stack.execute(InsertLine("window", "column", 1))
    stack.execute(InsertLine("window", "column", 2))
    label = add(stack, row=0, column=2)
    assert_undo_restores(stack, RemoveLine("window", "column", 1))
    assert stack.project.find(label.id).layout.column == 1
    with pytest.raises(CommandError):
        stack.execute(RemoveLine("window", "column", 1))  # nicht leer


def test_remove_last_line_fails(stack):
    with pytest.raises(CommandError):
        stack.execute(RemoveLine("window", "row", 0))


def test_set_line_config(stack):
    assert_undo_restores(stack, SetLineConfig("window", "column", 0, 1, 0, ""))
    assert stack.project.window.grid.columns[0] == LineConfig(weight=1)
    with pytest.raises(CommandError):
        stack.execute(SetLineConfig("window", "column", 3, 1, 0, ""))
    with pytest.raises(CommandError):
        stack.execute(SetLineConfig("window", "column", 0, -1, 0, ""))


def test_dirty_tracking(stack):
    assert not stack.dirty
    add(stack)
    assert stack.dirty
    stack.mark_saved()
    assert not stack.dirty
    stack.undo()
    assert stack.dirty
    stack.redo()
    assert not stack.dirty
    stack.undo()
    add(stack)  # neuer Zweig: gespeicherter Zustand nicht mehr erreichbar
    assert stack.dirty


def test_execute_notifies(stack):
    calls = []
    stack.project.subscribe(lambda: calls.append(1))
    add(stack)
    stack.undo()
    stack.redo()
    assert calls == [1, 1, 1]
