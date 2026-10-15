"""Freies Platzieren: Modell, Befehle, Export und Dateiformat (ohne Oberfläche)."""

import json

import pytest

from conftest import build_kontakt, grid_project
from ctk_builder import codegen, geometry, project_io
from ctk_builder.commands import (
    AddWidget, CommandError, CommandStack, DuplicateWidget, InsertLine, MoveWidget,
    RemoveLine, Restack, SetGeometry, SetLayout, SetLineConfig, SetManager, SetProperty,
)
from ctk_builder.geometry import Rect
from ctk_builder.model import GRID, PLACE, new_project


@pytest.fixture
def stack():
    return CommandStack(new_project())


def add(stack, widget_type, parent="window", **kwargs):
    command = AddWidget(parent, widget_type, **kwargs)
    stack.execute(command)
    return stack.project.find(command.node_id)


def test_new_projects_place_freely_and_frames_inherit(stack):
    assert stack.project.window.manager == PLACE
    frame = add(stack, "CTkFrame")
    assert frame.manager == PLACE
    grid_stack = CommandStack(grid_project())
    assert add(grid_stack, "CTkFrame").manager == GRID


def test_add_at_position_as_given(stack):
    button = add(stack, "CTkButton", x=50, y=60)
    assert (button.layout.x, button.layout.y) == (50, 60)
    # die Arbeitsfläche begrenzt mit echten Größen; der Befehl prüft nur x, y >= 0
    far = add(stack, "CTkButton", x=390, y=290)
    assert (far.layout.x, far.layout.y) == (390, 290)
    for x, y in ((-1, 0), (0, True), (1.5, 2)):
        with pytest.raises(CommandError):
            stack.execute(AddWidget("window", "CTkButton", x=x, y=y))


def test_add_without_position_goes_below(stack):
    first = add(stack, "CTkButton")
    second = add(stack, "CTkButton")
    assert (first.layout.x, first.layout.y) == (geometry.MARGIN, geometry.MARGIN)
    assert (second.layout.x, second.layout.y) == (geometry.MARGIN, 16 + 28 + geometry.GAP)
    # unter dem gewählten Widget, mit gemessenen Größen statt Schätzung
    wide = add(stack, "CTkButton", x=200, y=40)
    rects = {wide.id: Rect(200, 40, 210, 33), "window": Rect(0, 0, 400, 300)}
    third = add(stack, "CTkLabel", anchor=wide.id, rects=rects)
    assert (third.layout.x, third.layout.y) == (200, 40 + 33 + geometry.GAP)


def test_full_container_falls_back_to_free_spot(stack):
    for _ in range(40):
        add(stack, "CTkTextbox")  # 200 x 100 – passt nicht 40-mal hinein
    last = stack.project.window.children[-1]
    window = stack.project.window
    assert 0 <= last.layout.x <= window.width - 200
    assert 0 <= last.layout.y <= window.height - 100


def test_move_within_and_between_free_containers(stack):
    frame = add(stack, "CTkFrame", x=100, y=50)
    label = add(stack, "CTkLabel", x=10, y=10)
    stack.execute(MoveWidget(label.id, "window", x=30, y=40))
    label = stack.project.find(label.id)
    assert (label.layout.x, label.layout.y) == (30, 40)
    stack.execute(MoveWidget(label.id, frame.id, x=12, y=14))
    assert stack.project.parent_of(label.id).id == frame.id
    stack.undo()
    assert stack.project.parent_of(label.id).id == "window"
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(frame.id, frame.id, x=0, y=0))


def test_move_in_same_container_keeps_stacking_order(stack):
    a = add(stack, "CTkButton", x=20, y=20)
    b = add(stack, "CTkButton", x=60, y=60)
    stack.execute(MoveWidget(a.id, "window", x=100, y=100))
    assert [c.id for c in stack.project.window.children] == [a.id, b.id]


def test_move_between_free_and_grid_containers():
    stack = CommandStack(new_project())
    grid_frame = add(stack, "CTkFrame", x=150, y=20)
    stack.execute(SetManager(grid_frame.id, GRID))
    label = add(stack, "CTkLabel", x=10, y=10)
    add(stack, "CTkLabel", parent=grid_frame.id)
    # belegte Zelle: kein Tausch über die Anordnungen hinweg
    with pytest.raises(CommandError, match="belegt"):
        stack.execute(MoveWidget(label.id, grid_frame.id, row=0, column=0))
    stack.execute(MoveWidget(label.id, grid_frame.id, row=0, column=1))
    assert stack.project.parent_of(label.id).id == grid_frame.id
    with pytest.raises(CommandError):  # Raster-Ziel braucht eine Zelle
        stack.execute(MoveWidget(label.id, grid_frame.id))
    stack.execute(MoveWidget(label.id, "window", x=5, y=6))
    label = stack.project.find(label.id)
    assert (label.layout.x, label.layout.y) == (5, 6)


def test_grid_frame_moved_into_free_container_keeps_its_size():
    stack = CommandStack(grid_project())
    frame = add(stack, "CTkFrame")
    add(stack, "CTkLabel", parent=frame.id)
    target = add(stack, "CTkFrame")
    stack.execute(SetManager(target.id, PLACE))
    stack.execute(MoveWidget(frame.id, target.id, x=4, y=4,
                             rects={frame.id: Rect(0, 0, 61, 40)}))
    frame = stack.project.find(frame.id)
    assert (frame.props["width"], frame.props["height"]) == (61, 40)


def test_set_layout_position_without_grid_checks(stack):
    a = add(stack, "CTkButton", x=20, y=20)
    b = add(stack, "CTkButton", x=200, y=20)
    stack.execute(SetLayout(b.id, x=20, y=20))  # Überlappen ist im freien Modus erlaubt
    assert stack.project.find(b.id).layout.x == 20
    with pytest.raises(CommandError):
        stack.execute(SetLayout(a.id, x=-5))


def test_set_geometry(stack):
    button = add(stack, "CTkButton", x=20, y=20)
    stack.execute(SetGeometry(button.id, 30, 40, 180, 36))
    button = stack.project.find(button.id)
    assert (button.layout.x, button.layout.y) == (30, 40)
    assert (button.props["width"], button.props["height"]) == (180, 36)
    checkbox = add(stack, "CTkCheckBox")
    with pytest.raises(CommandError):  # keine width/height-Eigenschaft
        stack.execute(SetGeometry(checkbox.id, 0, 0, 50, 20))
    with pytest.raises(CommandError):
        stack.execute(SetGeometry(button.id, 0, 0, 0, 20))


def test_duplicate_is_offset_and_never_on_top_of_original(stack):
    button = add(stack, "CTkButton", x=20, y=30)
    command = DuplicateWidget(button.id)
    stack.execute(command)
    clone = stack.project.find(command.new_node_id)
    assert (clone.layout.x, clone.layout.y) == (36, 46)
    corner = add(stack, "CTkButton", x=260, y=272)  # rechts unten in 400 x 300
    command = DuplicateWidget(corner.id)
    stack.execute(command)
    clone = stack.project.find(command.new_node_id)
    assert (clone.layout.x, clone.layout.y) == (244, 256)


def test_grid_line_commands_refused_in_free_container(stack):
    for command in (InsertLine("window", "row", 0), RemoveLine("window", "row", 0),
                    SetLineConfig("window", "row", 0, 1, 0, "")):
        with pytest.raises(CommandError):
            stack.execute(command)


def test_grid_to_free_keeps_measured_geometry():
    project = build_kontakt()
    stack = CommandStack(project)
    entry = next(w for w in project.iter_widgets() if w.name == "entry_name")  # sticky ew
    label = next(w for w in project.iter_widgets() if w.name == "label_name")
    rects = {entry.id: Rect(70, 4, 330, 28), label.id: Rect(8, 4, 45, 28)}
    stack.execute(SetManager("window", PLACE, rects))
    entry = stack.project.find(entry.id)
    label = stack.project.find(label.id)
    assert stack.project.window.manager == PLACE
    assert (entry.layout.x, entry.layout.y, entry.props["width"]) == (70, 4, 330)
    assert (label.layout.x, label.layout.y) == (8, 4)
    assert "width" not in label.props  # nicht gestreckt: Größe bleibt automatisch
    # nicht gemessene Kinder landen an freien Stellen, nicht alle auf (0, 0)
    others = [c for c in stack.project.window.children if c.id not in rects]
    spots = {(c.layout.x, c.layout.y) for c in others}
    assert len(spots) == len(others)
    stack.undo()
    assert stack.project.window.manager == GRID


def test_grid_frame_to_free_keeps_its_size():
    stack = CommandStack(grid_project())
    frame = add(stack, "CTkFrame")
    stack.execute(SetManager(frame.id, PLACE, {frame.id: Rect(0, 0, 260, 48)}))
    frame = stack.project.find(frame.id)
    assert (frame.props["width"], frame.props["height"]) == (260, 48)


def cells_of(children, rects):
    cells, rows, columns = geometry.grid_cells(children, rects)
    return {k: (v["row"], v["column"], v["rowspan"], v["columnspan"])
            for k, v in cells.items()}, rows, columns


def test_free_to_grid_rows_by_position(stack):
    a = add(stack, "CTkLabel", x=20, y=20)
    b = add(stack, "CTkEntry", x=120, y=18)
    c = add(stack, "CTkButton", x=20, y=80)
    stack.execute(SetManager("window", GRID))
    cells = {n.id: (n.layout.row, n.layout.column) for n in stack.project.window.children}
    assert cells == {a.id: (0, 0), b.id: (0, 1), c.id: (1, 0)}
    grid = stack.project.window.grid
    assert (len(grid.rows), len(grid.columns)) == (2, 2)
    assert all(fits_ok(stack.project.window, n) for n in stack.project.window.children)
    with pytest.raises(CommandError):
        stack.execute(SetManager("window", GRID))


def fits_ok(container, node):
    from ctk_builder.model import fits
    return fits(container, node.layout, frozenset({node.id}))


def test_grid_cells_tall_widget_spans_rows():
    """Textbox 200 x 100 links, drei Labels rechts daneben."""
    stack = CommandStack(new_project())
    tall = add(stack, "CTkTextbox", x=20, y=20)
    labels = [add(stack, "CTkLabel", x=240, y=y) for y in (20, 50, 80)]
    rects = {tall.id: Rect(20, 20, 200, 100)}
    rects.update({n.id: Rect(240, n.layout.y, 31, 28) for n in labels})
    cells, rows, columns = cells_of(stack.project.window.children, rects)
    assert cells[tall.id] == (0, 0, 3, 1)
    assert [cells[n.id] for n in labels] == [(0, 1, 1, 1), (1, 1, 1, 1), (2, 1, 1, 1)]
    assert (rows, columns) == (3, 2)


def test_grid_cells_keeps_columns_across_rows_and_spans_wide_widgets():
    stack = CommandStack(new_project())
    label = add(stack, "CTkLabel", x=20, y=20)
    entry = add(stack, "CTkEntry", x=120, y=20)
    lone = add(stack, "CTkEntry", x=120, y=60)       # Zeile ohne Label
    long_label = add(stack, "CTkLabel", x=20, y=100)
    wide = add(stack, "CTkButton", x=20, y=140)      # breit wie Label + Entry
    rects = {label.id: Rect(20, 20, 60, 28), entry.id: Rect(120, 20, 140, 28),
             lone.id: Rect(120, 60, 140, 28), long_label.id: Rect(20, 100, 90, 28),
             wide.id: Rect(20, 140, 240, 28)}
    cells, rows, columns = cells_of(stack.project.window.children, rects)
    assert cells[lone.id] == (1, 1, 1, 1)
    assert cells[wide.id] == (3, 0, 1, 2)
    assert (rows, columns) == (4, 2)
    layout = geometry.grid_cells(stack.project.window.children, rects)[0]
    assert layout[label.id]["sticky"] == "nsw"   # links bündig, schmaler als die Spalte
    assert layout[long_label.id]["sticky"] == "nsew"
    assert layout[entry.id]["sticky"] == "nsew"


def test_grid_cells_resolves_overlap():
    assert geometry.grid_cells([]) == ({}, 1, 1)
    stack = CommandStack(new_project())
    a = add(stack, "CTkButton", x=20, y=20)
    b = add(stack, "CTkButton", x=20, y=20)  # genau übereinander
    stack.execute(SetManager("window", GRID))
    window = stack.project.window
    assert all(fits_ok(window, n) for n in window.children)
    positions = {(n.layout.row, n.layout.column) for n in window.children}
    assert len(positions) == 2


def test_size_hint():
    stack = CommandStack(new_project())
    assert geometry.size_hint(add(stack, "CTkButton")) == (140, 28)
    assert geometry.size_hint(add(stack, "CTkTextbox")) == (200, 100)
    label = add(stack, "CTkLabel")
    width, height = geometry.size_hint(label)
    assert 20 <= width <= 60 and height == 28
    stack.execute(SetProperty(label.id, "text", "Ein ziemlich langer Text"))
    assert geometry.size_hint(stack.project.find(label.id))[0] > width
    checkbox = add(stack, "CTkCheckBox")
    assert geometry.size_hint(checkbox) == (100, 24)


# ---------------------------------------------------------------- Export

def test_codegen_place(stack):
    frame = add(stack, "CTkFrame", x=100, y=50)
    add(stack, "CTkButton", parent=frame.id, x=10, y=12)
    stack.execute(SetGeometry(stack.project.window.children[0].children[0].id, 10, 12, 160, 32))
    source = codegen.generate_ui(stack.project, "app")
    assert "self.frame_1.place(x=100, y=50)" in source
    assert "self.button_1.place(x=10, y=12)" in source
    assert "width=160" in source and "height=32" in source
    assert "grid" not in source
    compile(source, "app_ui.py", "exec")


def test_codegen_mixed_grid_frame_in_free_window(stack):
    frame = add(stack, "CTkFrame", x=40, y=40)
    stack.execute(SetManager(frame.id, GRID))
    add(stack, "CTkLabel", parent=frame.id)
    source = codegen.generate_ui(stack.project, "app")
    assert "self.frame_1.place(x=40, y=40)" in source
    assert "self.label_1.grid(row=0, column=0)" in source
    # frei platziert behält der Raster-Frame seine Größe (wie auf der Arbeitsfläche)
    assert "self.frame_1.grid_propagate(False)" in source


# ---------------------------------------------------------------- Dateiformat

def test_roundtrip_keeps_manager_and_position(stack, tmp_path):
    frame = add(stack, "CTkFrame", x=100, y=50)
    stack.execute(SetManager(frame.id, GRID))
    add(stack, "CTkLabel", x=33, y=44)
    path = tmp_path / "frei.ctkb.json"
    project_io.save(stack.project, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format_version"] == 2
    loaded = project_io.load(path)
    assert loaded.window.manager == PLACE
    assert loaded.window.children[0].manager == GRID
    label = loaded.window.children[1]
    assert (label.layout.x, label.layout.y) == (33, 44)


def test_pure_grid_project_saves_as_format_1_and_loads_back():
    data = project_io.to_dict(build_kontakt())
    assert data["format_version"] == 1
    loaded = project_io.from_dict(data)
    assert loaded.window.manager == GRID
    assert project_io.to_dict(loaded) == data


def test_format_1_files_load_as_grid():
    data = project_io.to_dict(build_kontakt())
    data["format_version"] = 1
    for node in [data["window"], *_walk(data["window"])]:
        node.pop("manager", None)
        node.get("layout", {}).pop("x", None)
        node.get("layout", {}).pop("y", None)
    project = project_io.from_dict(data)
    assert project.window.manager == GRID
    assert all(w.manager == GRID for w in project.iter_widgets() if w.is_container)
    assert all(w.manager is None for w in project.iter_widgets() if not w.is_container)


def _walk(node):
    for child in node["children"]:
        yield child
        yield from _walk(child)


@pytest.mark.parametrize("change", [
    lambda d: d["window"].update(manager="pack"),
    lambda d: d["window"].pop("manager"),
    lambda d: d["window"]["children"][0]["layout"].update(x="12"),
    lambda d: d["window"]["children"][0]["layout"].update(x=-3),
    lambda d: d["window"]["children"][0]["layout"].update(y=True),
    lambda d: d.update(format_version=True),
    lambda d: d.update(format_version=0),
])
def test_invalid_free_layout_data_is_rejected(change):
    stack = CommandStack(new_project())
    add(stack, "CTkLabel", x=1, y=2)
    data = project_io.to_dict(stack.project)
    change(data)
    with pytest.raises(project_io.ProjectFileError):
        project_io.from_dict(data)


def test_restack_reorders_children_and_export(stack):
    a = add(stack, "CTkButton", x=20, y=20)
    b = add(stack, "CTkButton", x=40, y=40)
    c = add(stack, "CTkButton", x=60, y=60)
    order = lambda: [n.id for n in stack.project.window.children]  # noqa: E731
    stack.execute(Restack(a.id, "front"))
    assert order() == [b.id, c.id, a.id]
    stack.execute(Restack(a.id, "backward"))
    assert order() == [b.id, a.id, c.id]
    stack.execute(Restack(c.id, "back"))
    assert order() == [c.id, b.id, a.id]
    with pytest.raises(CommandError):
        stack.execute(Restack(c.id, "backward"))
    source = codegen.generate_ui(stack.project, "app")
    assert source.index("button_3 =") < source.index("button_2 =") < source.index("button_1 =")
    stack.undo()
    assert order() == [b.id, a.id, c.id]


def test_set_manager_recursive_in_one_step():
    stack = CommandStack(grid_project())
    frame = add(stack, "CTkFrame")
    inner = add(stack, "CTkFrame", parent=frame.id)
    add(stack, "CTkLabel", parent=inner.id)
    steps = len(stack._undo)
    stack.execute(SetManager("window", PLACE, recursive=True))
    project = stack.project
    assert project.window.is_free
    assert all(w.is_free for w in project.iter_widgets() if w.is_container)
    assert len(stack._undo) == steps + 1
    stack.undo()
    assert not any(w.is_free for w in project.iter_widgets() if w.is_container)


def test_set_layout_on_grid_child_ignores_stale_position():
    stack = CommandStack(grid_project())
    label = add(stack, "CTkLabel")
    stack.project.find(label.id).layout.x = -3  # alter Wert, im Raster bedeutungslos
    stack.execute(SetLayout(label.id, sticky="w"))
    assert stack.project.find(label.id).layout.sticky == "w"


@pytest.mark.parametrize("layout", ["column", "row", "chain", "form"])
def test_grid_conversion_stays_fast_with_many_widgets(layout):
    """Regression: die Band-Suche war exponentiell (15 bündige Widgets: 10 s)."""
    import time

    stack = CommandStack(new_project())
    stack.execute(__import__("ctk_builder.commands", fromlist=["SetWindowProperty"])
                  .SetWindowProperty("height", 3000))
    rects = {}
    for i in range(40):
        x, y, width = {"column": (16, 16 + 36 * i, 140), "row": (16 + 150 * i, 16, 140),
                       "chain": (16 + 20 * i, 16 + 20 * i, 140),
                       "form": (16 + 120 * (i % 2), 16 + 36 * (i // 2), 100)}[layout]
        node = add(stack, "CTkButton", x=x, y=y)
        rects[node.id] = Rect(x, y, width, 28)
    started = time.perf_counter()
    stack.execute(SetManager("window", GRID, rects))
    assert time.perf_counter() - started < 1.0
    window = stack.project.window
    assert all(fits_ok(window, n) for n in window.children)


def test_move_from_free_into_grid_starts_with_fresh_grid_values():
    stack = CommandStack(grid_project())
    label = add(stack, "CTkLabel")
    stack.execute(SetLayout(label.id, columnspan=1, sticky="ew", padx=9))
    frame = add(stack, "CTkFrame")
    stack.execute(SetManager(frame.id, PLACE))
    stack.execute(MoveWidget(label.id, frame.id, x=5, y=5))
    stack.execute(MoveWidget(label.id, "window", row=2, column=0))  # neue Zeile
    layout = stack.project.find(label.id).layout
    assert (layout.rowspan, layout.columnspan, layout.sticky, layout.padx) == (1, 1, "", 0)


def test_move_stretched_widget_from_grid_into_free_keeps_visible_width():
    stack = CommandStack(grid_project())
    entry = add(stack, "CTkEntry")
    stack.execute(SetLayout(entry.id, sticky="ew"))
    frame = add(stack, "CTkFrame")
    stack.execute(SetManager(frame.id, PLACE))
    stack.execute(MoveWidget(entry.id, frame.id, x=0, y=0,
                             rects={entry.id: Rect(0, 0, 280, 28)}))
    assert stack.project.find(entry.id).props["width"] == 280


def test_spot_below_skips_widgets_in_the_way(stack):
    label = add(stack, "CTkLabel", x=20, y=20)
    button = add(stack, "CTkButton", x=20, y=60)
    rects = {label.id: Rect(20, 20, 40, 28), button.id: Rect(20, 60, 140, 28),
             "window": Rect(0, 0, 400, 300)}
    entry = add(stack, "CTkEntry", anchor=label.id, rects=rects, size=(140, 28))
    assert (entry.layout.x, entry.layout.y) == (20, 60 + 28 + geometry.GAP)
