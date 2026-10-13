from ctk_builder.model import (
    GridConfig, Layout, LineConfig, Project, WidgetNode, fits, next_free_cell, occupant,
)


def make_widget(id_, name, row=0, column=0, rowspan=1, columnspan=1, grid=None):
    return WidgetNode(
        id=id_, type="CTkLabel", name=name,
        layout=Layout(row=row, column=column, rowspan=rowspan, columnspan=columnspan),
        grid=grid,
    )


def test_new_project_has_window_with_one_cell():
    project = Project()
    assert project.window.id == "window"
    assert len(project.window.grid.rows) == 1
    assert len(project.window.grid.columns) == 1
    assert project.window.children == []


def test_layout_cells_covers_span():
    layout = Layout(row=1, column=2, rowspan=2, columnspan=2)
    assert layout.cells() == {(1, 2), (1, 3), (2, 2), (2, 3)}


def test_line_config_default():
    assert LineConfig().is_default()
    assert not LineConfig(weight=1).is_default()


def test_occupant_and_fits():
    project = Project()
    window = project.window
    window.grid = GridConfig(rows=[LineConfig()] * 2, columns=[LineConfig()] * 2)
    window.children.append(make_widget("a", "label_1", columnspan=2))
    assert occupant(window, 0, 1).id == "a"
    assert occupant(window, 1, 0) is None
    assert fits(window, Layout(row=1, column=0))
    assert not fits(window, Layout(row=0, column=1))
    assert fits(window, Layout(row=0, column=1), ignore=frozenset({"a"}))
    assert not fits(window, Layout(row=1, column=1, columnspan=2))  # außerhalb


def test_next_free_cell_scans_rows_then_appends():
    project = Project()
    window = project.window
    assert next_free_cell(window) == (0, 0)
    window.children.append(make_widget("a", "label_1"))
    assert next_free_cell(window) == (1, 0)


def test_find_parent_descendant_and_iteration_order():
    project = Project()
    frame = make_widget("f", "frame_1", grid=GridConfig())
    inner = make_widget("i", "label_2")
    frame.children.append(inner)
    project.window.children += [frame, make_widget("b", "label_1", row=1)]

    assert [w.id for w in project.iter_widgets()] == ["f", "i", "b"]
    assert project.find("i") is inner
    assert project.find("window") is project.window
    assert project.find("nope") is None
    assert project.parent_of("i") is frame
    assert project.parent_of("f") is project.window
    assert project.is_descendant("i", "f")
    assert project.is_descendant("f", "f")
    assert not project.is_descendant("f", "i")


def test_unique_name():
    project = Project()
    project.window.children.append(make_widget("a", "label_1"))
    assert project.unique_name("label") == "label_2"
    assert project.unique_name("button") == "button_1"


def test_subscribe_and_unsubscribe():
    project = Project()
    calls = []
    unsubscribe = project.subscribe(lambda: calls.append(1))
    project.notify()
    unsubscribe()
    project.notify()
    assert calls == [1]
