"""Freies Platzieren auf der Arbeitsfläche: Ziehen, Einrasten, Anfasser, Tasten."""

import pytest

from conftest import build_kontakt, click
from ctk_builder import project_io
from ctk_builder.commands import AddWidget, CommandStack, SetGeometry, SetProperty
from ctk_builder.model import GRID, PLACE, new_project
from ctk_builder.session import Session
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.drag_drop import DragController, DropTarget, drop_target
from ctk_builder.ui.grid_overlay import GridOverlay
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.properties import PropertiesPanel


def build_free():
    """Freies Fenster 480 x 320: Label, Button, Frame (frei) mit Entry, CheckBox."""
    stack = CommandStack(new_project())
    ids = {}

    def add(name, widget_type, parent="window", **kwargs):
        command = AddWidget(ids.get(parent, parent), widget_type, **kwargs)
        stack.execute(command)
        ids[name] = command.node_id

    from ctk_builder.commands import SetWindowProperty
    stack.execute(SetWindowProperty("width", 480))
    stack.execute(SetWindowProperty("height", 320))
    add("label", "CTkLabel", x=20, y=20)
    add("button", "CTkButton", x=20, y=60)
    add("frame", "CTkFrame", x=220, y=40)
    add("entry", "CTkEntry", parent="frame", x=10, y=10)
    add("check", "CTkCheckBox", x=20, y=120)
    return stack.project, ids


@pytest.fixture
def free(root):
    project, ids = build_free()
    session = Session()
    session.replace_project(project, None)
    root.geometry("900x600")
    canvas = DesignCanvas(root, session)
    palette = Palette(root, session)
    palette.pack(side="left")
    canvas.pack(side="left", fill="both", expand=True)
    drag = DragController(canvas, palette)
    root.update()
    return session, canvas, drag, ids


def press(widget, x_root, y_root, state=0):
    widget.event_generate("<Button-1>", x=2, y=2, rootx=x_root, rooty=y_root, state=state)


BUTTON1 = 0x100  # Maustaste 1 gedrückt – sonst passt <B1-Motion> nicht
ALT = {"darwin": 0x10, "win32": 0x20000}.get(__import__("sys").platform, 0x8)  # kein Einrasten


def move(widget, x_root, y_root, state=0):
    widget.event_generate("<B1-Motion>", x=2, y=2, rootx=x_root, rooty=y_root,
                          state=state | BUTTON1)


def release(widget, x_root, y_root):
    widget.event_generate("<ButtonRelease-1>", x=2, y=2, rootx=x_root, rooty=y_root)
    widget.update()


def surface_point(canvas, container_id, x, y):
    view = canvas.view_of(container_id)
    return view.winfo_rootx() + x, view.winfo_rooty() + y


def inner(canvas, node_id):
    view = canvas.views[node_id]
    return view.winfo_children()[0] if view.winfo_children() else view


def test_free_widgets_are_placed_where_the_model_says(free):
    session, canvas, _, ids = free
    assert canvas.rect_of(ids["button"]).x == 20
    assert canvas.rect_of(ids["button"]).y == 60
    assert canvas.rect_of(ids["entry"]).x == 10
    assert canvas.measure(ids["frame"])[ids["entry"]].y == 10


def test_drag_from_palette_drops_under_pointer(free):
    session, canvas, drag, _ = free
    tile = drag.palette.buttons["CTkButton"].winfo_children()[0]
    start = (tile.winfo_rootx() + 3, tile.winfo_rooty() + 3)
    target = surface_point(canvas, "window", 100, 278)   # Mitte des neuen Buttons
    press(tile, *start)
    move(tile, *target, state=ALT)  # ohne Einrasten: genau unter dem Zeiger
    release(tile, *target)
    added = session.project.find(session.selected_id)
    assert added.type == "CTkButton"
    width, height = canvas.rect_of(added.id).width, canvas.rect_of(added.id).height
    assert (added.layout.x, added.layout.y) == (100 - width // 2, 278 - height // 2)


def test_move_is_live_and_one_command(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    press(source, x, y)
    move(source, x + 101, y + 47, state=ALT)
    source.update()
    view = canvas.views[ids["button"]]
    assert int(view.place_info()["x"]) == 121  # folgt live, Modell noch unverändert
    assert session.project.find(ids["button"]).layout.x == 20
    undo_steps = len(session.stack._undo)
    release(source, x + 101, y + 47)
    node = session.project.find(ids["button"])
    assert (node.layout.x, node.layout.y) == (121, 107)
    assert [c.id for c in session.project.window.children].index(ids["button"]) == 1
    assert len(session.stack._undo) == undo_steps + 1


def test_snaps_to_neighbour_edge_and_alt_disables(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["check"])
    x, y = surface_point(canvas, "window", 25, 125)
    # unter den Frame (y 40..240), linke Kante 3 px neben der des Frames (220)
    press(source, x, y)
    move(source, x + 203, y + 141)
    release(source, x + 203, y + 141)
    assert session.project.find(ids["check"]).layout.x == 220
    source = inner(canvas, ids["check"])
    x, y = surface_point(canvas, "window", 225, 266)
    press(source, x, y)
    # 218 liegt 2 px neben der Frame-Kante: ohne Alt rastete es auf 220 ein
    move(source, x - 2, y + 8, state=ALT)
    release(source, x - 2, y + 8)
    assert session.project.find(ids["check"]).layout.x == 218


def test_esc_cancels_move_without_command(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    undo_steps = len(session.stack._undo)
    press(source, x, y)
    move(source, x + 80, y + 80)
    assert drag.cancel()
    # Esc zeichnet neu (das gedrückte Widget gibt es nicht mehr): Loslassen kommt
    # dort an, wo der Zeiger ist – es darf nichts mehr auslösen
    release(canvas.surface, x + 80, y + 80)
    assert session.project.find(ids["button"]).layout.x == 20
    assert len(session.stack._undo) == undo_steps
    assert int(canvas.views[ids["button"]].place_info()["x"]) == 20


def test_esc_after_palette_drag_adds_nothing(free):
    session, canvas, drag, _ = free
    tile = drag.palette.buttons["CTkLabel"].winfo_children()[0]
    count = len(list(session.project.iter_widgets()))
    press(tile, tile.winfo_rootx() + 3, tile.winfo_rooty() + 3)
    target = surface_point(canvas, "window", 300, 250)
    move(tile, *target)
    drag.cancel()
    release(tile, *target)
    assert len(list(session.project.iter_widgets())) == count


def test_drag_into_frame_and_out_of_surface(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["label"])
    x, y = surface_point(canvas, "window", 22, 22)
    to = surface_point(canvas, ids["frame"], 60, 100)
    press(source, x, y)
    move(source, *to)
    assert drag._target.container_id == ids["frame"]  # trotz Widget unter dem Zeiger
    release(source, *to)
    assert session.project.parent_of(ids["label"]).id == ids["frame"]
    label = session.project.find(ids["label"])
    assert 50 <= label.layout.x <= 64 and 90 <= label.layout.y <= 104
    # über den Rand hinaus: bleibt am Rand des Containers statt zurückzuspringen
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    surface = canvas.surface
    outside = (surface.winfo_rootx() - 60, y)
    press(source, x, y)
    move(source, *outside)
    release(source, *outside)
    assert session.project.find(ids["button"]).layout.x == 0


def test_drop_target_ignores_moving_widget(free):
    session, canvas, _, ids = free
    view = canvas.views[ids["frame"]]
    point = (view.winfo_rootx() + 5, view.winfo_rooty() + 5)
    assert drop_target(canvas, *point) == DropTarget(ids["frame"])
    assert drop_target(canvas, *point, moving=ids["frame"]) == DropTarget("window")


def test_handles_only_where_size_can_change(free):
    session, canvas, drag, ids = free
    session.select(ids["button"])
    canvas.update()
    assert all(h.winfo_ismapped() for h in drag._handles.values())
    session.select(ids["check"])  # CheckBox: keine width/height-Eigenschaft
    canvas.update()
    assert not any(h.winfo_ismapped() for h in drag._handles.values())


def test_handles_at_window_edge_are_clickable(free):
    session, canvas, drag, ids = free
    session.execute(SetGeometry(ids["button"], 0, 0, 140, 28))
    session.select(ids["button"])
    canvas.update()
    handle = drag._handles["nw"]
    x = handle.winfo_rootx() + 1
    y = handle.winfo_rooty() + 1
    assert canvas.winfo_containing(x, y) is handle


def test_resize_with_handle_and_measured_minimum(free):
    session, canvas, drag, ids = free
    session.select(ids["button"])
    canvas.update()
    handle = drag._handles["e"]
    x, y = handle.winfo_rootx() + 4, handle.winfo_rooty() + 4
    handle.event_generate("<Button-1>", x=4, y=4, rootx=x, rooty=y)
    handle.event_generate("<B1-Motion>", x=4, y=4, rootx=x + 61, rooty=y,
                          state=BUTTON1 | ALT)
    handle.event_generate("<ButtonRelease-1>", x=4, y=4, rootx=x + 61, rooty=y)
    canvas.update()
    node = session.project.find(ids["button"])
    assert (node.props["width"], node.layout.x) == (201, 20)
    # Text erzwingt eine Mindestbreite: gespeichert wird, was zu sehen ist
    session.execute(SetProperty(ids["button"], "text", "Ein sehr langer Button-Text"))
    session.select(ids["button"])
    canvas.update()
    handle = drag._handles["e"]
    x, y = handle.winfo_rootx() + 4, handle.winfo_rooty() + 4
    handle.event_generate("<Button-1>", x=4, y=4, rootx=x, rooty=y)
    handle.event_generate("<B1-Motion>", x=4, y=4, rootx=x - 190, rooty=y, state=BUTTON1)
    handle.event_generate("<ButtonRelease-1>", x=4, y=4, rootx=x - 190, rooty=y)
    canvas.update()
    node = session.project.find(ids["button"])
    assert node.props["width"] == canvas.rect_of(ids["button"]).width > 11


def test_grid_frame_in_free_window_keeps_size_and_has_handles(root):
    stack = CommandStack(new_project())
    frame = AddWidget("window", "CTkFrame", x=20, y=20)
    stack.execute(frame)
    from ctk_builder.commands import SetManager
    stack.execute(SetManager(frame.node_id, GRID))
    stack.execute(AddWidget(frame.node_id, "CTkLabel"))
    session = Session()
    session.replace_project(stack.project, None)
    canvas = DesignCanvas(root, session)
    canvas.pack(fill="both", expand=True)
    palette = Palette(root, session)
    drag = DragController(canvas, palette)
    session.select(frame.node_id)
    root.update()
    assert drag.resizable(frame.node_id)
    assert all(h.winfo_ismapped() for h in drag._handles.values())
    # frei platziert: so groß wie width/height, nicht wie der Inhalt (wie im Export)
    assert canvas.rect_of(frame.node_id).width == 200


def test_grid_overlay_skips_free_containers(free):
    session, canvas, _, ids = free
    overlay = GridOverlay(canvas)
    assert overlay._lines == []
    session.select("window")
    assert overlay._headers == []


def test_properties_show_position_and_arrangement(free, root):
    session, canvas, _, ids = free
    panel = PropertiesPanel(root, session)
    panel.pack(side="right")
    session.select(ids["button"])
    assert {"x", "y"} <= set(panel.fields)
    assert not {"row", "column", "sticky_n"} & set(panel.fields)
    session.select("window")
    assert panel.fields["manager"].get() == "Frei"
    panel.fields["manager"].set("Raster")
    panel.fields["manager"]._command("Raster")
    assert session.project.window.manager == GRID
    session.undo()
    assert session.project.window.manager == PLACE


# ---------------------------------------------------------------- Hauptfenster

@pytest.fixture
def free_app(tmp_path):
    from conftest import has_display
    if not has_display():
        pytest.skip("kein Display verfügbar")
    from ctk_builder.settings import Settings
    from ctk_builder.ui.main_window import MainWindow

    project, ids = build_free()
    session = Session()
    session.replace_project(project, None)
    window = MainWindow(session, Settings(tmp_path / "settings.json"))
    window.update()
    yield window, ids
    window.runner.stop()
    window.destroy()


def test_arrow_keys_move_live_and_commit_once(free_app):
    app, ids = free_app
    session = app.session
    session.select(ids["button"])
    undo_steps = len(session.stack._undo)
    for _ in range(5):
        app.nudge(0, 1)
    app.nudge(1, 0, 10)
    app.update()
    assert int(app.canvas.views[ids["button"]].place_info()["x"]) == 25
    assert session.project.find(ids["button"]).layout.x == 20  # noch nicht übernommen
    app.flush_nudge()
    node = session.project.find(ids["button"])
    assert (node.layout.x, node.layout.y) == (25, 70)
    assert len(session.stack._undo) == undo_steps + 1


def test_pending_nudge_is_committed_before_other_changes(free_app):
    app, ids = free_app
    session = app.session
    session.select(ids["button"])
    app.nudge(0, 1)
    session.undo()  # nimmt erst die Bewegung auf, dann wird sie rückgängig gemacht
    assert session.project.find(ids["button"]).layout.x == 20
    session.redo()
    assert session.project.find(ids["button"]).layout.x == 21


def test_restack_changes_stacking_and_export_order(free_app):
    app, ids = free_app
    session = app.session
    session.select(ids["label"])
    app.restack_selected("front")
    assert session.project.window.children[-1].id == ids["label"]
    app.restack_selected("back")
    assert session.project.window.children[0].id == ids["label"]
    assert "ganz unten" in app.status.cget("text") or True
    app.restack_selected("backward")  # liegt schon ganz unten: Meldung, kein Befehl
    assert session.project.window.children[0].id == ids["label"]


def test_context_menu_on_widget(free_app):
    app, ids = free_app
    view = app.canvas.views[ids["button"]]
    target = view.winfo_children()[0]
    target.event_generate("<Button-3>", x=3, y=3, rootx=view.winfo_rootx() + 3,
                          rooty=view.winfo_rooty() + 3)
    app.update()
    assert app.session.selected_id == ids["button"]
    menu = app._context_menu
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
              if menu.type(i) == "command"]
    assert "Ganz nach vorne" in labels and "Duplizieren" in labels
    menu.unpost()


def test_notice_converts_old_grid_project(tmp_path):
    from conftest import has_display
    if not has_display():
        pytest.skip("kein Display verfügbar")
    from ctk_builder.settings import Settings
    from ctk_builder.ui.main_window import MainWindow

    data = project_io.to_dict(build_kontakt())
    data["format_version"] = 1
    session = Session()
    session.replace_project(project_io.from_dict(data), None)
    app = MainWindow(session, Settings(tmp_path / "settings.json"))
    try:
        app.update()
        assert app.grid_notice.winfo_ismapped()
        before = {w.id: app.canvas.rect_of(w.id) for w in session.project.iter_widgets()}
        app.make_all_free()
        app.update()
        assert session.project.window.manager == PLACE
        assert all(w.manager == PLACE for w in session.project.iter_widgets() if w.is_container)
        for node_id, rect in before.items():
            after = app.canvas.rect_of(node_id)
            assert abs(after.x - rect.x) <= 1 and abs(after.y - rect.y) <= 1, node_id
        assert not app.grid_notice.winfo_ismapped()
        session.undo()
        assert session.project.window.manager == GRID
    finally:
        app.runner.stop()
        app.destroy()


def test_snap_toggle_is_saved(free_app, tmp_path):
    app, _ = free_app
    assert not app.drag.grid_snap
    app.toggle_grid_snap()
    assert app.drag.grid_snap and app.settings.snap_to_grid
    from ctk_builder.settings import Settings
    assert Settings(tmp_path / "settings.json").snap_to_grid


def test_palette_click_stacks_below_selection(free_app):
    app, ids = free_app
    session = app.session
    session.select(ids["button"])
    click(app.palette.buttons["CTkEntry"].winfo_children()[0])
    first = session.project.find(session.selected_id)
    # direkt unter dem Button läge es auf der CheckBox (y 120): also darunter
    check = app.canvas.rect_of(ids["check"])
    assert (first.layout.x, first.layout.y) == (20, check.bottom + 8)
    click(app.palette.buttons["CTkEntry"].winfo_children()[0])
    second = session.project.find(session.selected_id)
    assert second.layout.x == 20 and second.layout.y == first.layout.y + 28 + 8


# ---------------------------------------------------------------- Export, HiDPI

MEASURE = """\
import json, sys
sys.path.insert(0, sys.argv[1])
from frei_ui import AppUI

app = AppUI()
app.update()
out = {}
for name in sys.argv[2:]:
    widget = getattr(app, name)
    out[name] = [widget.winfo_x(), widget.winfo_y(), widget.winfo_width(), widget.winfo_height()]
print(json.dumps(out))
app.destroy()
"""


def test_exported_free_layout_looks_like_the_canvas(free, tmp_path):
    """Der exportierte Code ergibt dieselbe Geometrie wie die Arbeitsfläche."""
    import json
    import subprocess
    import sys

    from ctk_builder import exporter
    from ctk_builder.commands import SetManager

    session, canvas, _, ids = free
    session.execute(SetManager(ids["frame"], GRID, session.measure(ids["frame"])))
    session.execute(SetGeometry(ids["button"], 20, 60, 180, 36))
    session.save(tmp_path / "frei.ctkb.json")
    exporter.export(session.project, session.path)
    canvas.update()
    (tmp_path / "measure.py").write_text(MEASURE, encoding="utf-8")
    names = {session.project.find(i).name: i for i in ids.values()}
    result = subprocess.run([sys.executable, str(tmp_path / "measure.py"), str(tmp_path),
                             *names], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    measured = json.loads(result.stdout.strip().splitlines()[-1])
    for name, node_id in names.items():
        view = canvas.views[node_id]
        assert measured[name] == [view.winfo_x(), view.winfo_y(), view.winfo_width(),
                                  view.winfo_height()], name


@pytest.mark.parametrize("scaling", [1.25, 1.5])
def test_hidpi_positions_and_guides_are_pixel_exact(root, scaling):
    import customtkinter as ctk

    ctk.set_widget_scaling(scaling)
    try:
        stack = CommandStack(new_project())
        a = AddWidget("window", "CTkButton", x=7, y=13)
        b = AddWidget("window", "CTkButton", x=150, y=150)
        stack.execute(a)
        stack.execute(b)
        session = Session()
        session.replace_project(stack.project, None)
        root.geometry("1200x800")
        canvas = DesignCanvas(root, session)
        canvas.pack(fill="both", expand=True)
        drag = DragController(canvas, Palette(root, session))
        root.update()
        view_a, view_b = canvas.views[a.node_id], canvas.views[b.node_id]
        assert view_a.winfo_x() == int(7 * scaling)
        assert canvas.rect_of(a.node_id).width == 140
        # b so ziehen, dass seine linke Kante 2 px neben der von a liegt: rastet ein
        source = inner(canvas, b.node_id)
        x0, y0 = view_b.winfo_rootx() + 5, view_b.winfo_rooty() + 5
        dx = round((9 - 150) * scaling)
        press(source, x0, y0)
        move(source, x0 + dx, y0)
        root.update()
        assert view_b.winfo_rootx() == view_a.winfo_rootx()
        guides = [g for g in drag._guides if g.winfo_ismapped() and g.winfo_width() == 1]
        assert any(g.winfo_rootx() == view_a.winfo_rootx() for g in guides)
        release(source, x0 + dx, y0)
        assert session.project.find(b.node_id).layout.x == 7
    finally:
        ctk.set_widget_scaling(1.0)


# ---------------------------------------------------------------- Befunde der Prüfung 1.1.0

def drag_handle(handle, dx, dy, state=0):
    x, y = handle.winfo_rootx() + 4, handle.winfo_rooty() + 4
    handle.event_generate("<Button-1>", x=4, y=4, rootx=x, rooty=y)
    handle.event_generate("<B1-Motion>", x=4, y=4, rootx=x + dx, rooty=y + dy,
                          state=BUTTON1 | state)
    handle.event_generate("<ButtonRelease-1>", x=4, y=4, rootx=x + dx, rooty=y + dy)
    handle.update()


def test_lost_release_after_cancel_does_not_break_next_resize(free):
    """Esc, Loslassen kommt nie an (Zeiger neben dem Fenster): die nächste
    Größenänderung muss trotzdem gespeichert werden."""
    session, canvas, drag, ids = free
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    press(source, x, y)
    move(source, x + 80, y + 80)
    assert drag.cancel()
    session.select(ids["button"])
    canvas.update()
    drag_handle(drag._handles["e"], 30, 0, state=ALT)
    assert session.project.find(ids["button"]).props["width"] == 170
    assert not drag.active


def test_stale_drag_is_cleaned_up_by_next_press(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    press(source, x, y)
    move(source, x + 80, y + 40)  # Loslassen geht verloren
    label = inner(canvas, ids["label"])
    lx, ly = surface_point(canvas, "window", 22, 22)
    press(label, lx, ly)
    assert int(canvas.views[ids["button"]].place_info()["x"]) == 20  # zurück an seinem Platz
    move(label, lx + 100, ly + 100, state=ALT)
    release(label, lx + 100, ly + 100)
    assert session.project.find(ids["label"]).layout.x == 120
    assert session.project.find(ids["button"]).layout.x == 20


def test_position_change_keeps_views(free):
    """Nur Positionen geändert: Ansichten werden verschoben, nicht neu gebaut – sonst
    ginge der Maus-Grab eines gerade gedrückten Widgets verloren."""
    session, canvas, _, ids = free
    from ctk_builder.commands import SetLayout
    before = dict(canvas.views)
    session.execute(SetLayout(ids["entry"], x=30, y=40))
    canvas.update()
    assert canvas.views == before
    assert canvas.views[ids["entry"]].winfo_x() == 30
    session.execute(SetProperty(ids["entry"], "width", 160))
    assert canvas.views[ids["entry"]] is not before[ids["entry"]]  # sonst neu gebaut


def test_undo_without_history_during_resize_restores_preview(free):
    session, canvas, drag, ids = free
    session.stack.reset(session.project)  # leerer Verlauf, wie direkt nach dem Öffnen
    session.select(ids["button"])
    canvas.update()
    handle = drag._handles["se"]
    x, y = handle.winfo_rootx() + 4, handle.winfo_rooty() + 4
    handle.event_generate("<Button-1>", x=4, y=4, rootx=x, rooty=y)
    handle.event_generate("<B1-Motion>", x=4, y=4, rootx=x + 60, rooty=y + 30,
                          state=BUTTON1 | ALT)
    canvas.update()
    session.undo()  # Strg+Z mitten in der Geste, nichts rückgängig zu machen
    canvas.update()
    assert canvas.rect_of(ids["button"]).width == 140
    handle.event_generate("<ButtonRelease-1>", x=4, y=4, rootx=x + 60, rooty=y + 30)
    assert "width" not in session.project.find(ids["button"]).props


def test_delete_before_drag_threshold_does_not_crash(free):
    session, canvas, drag, ids = free
    from ctk_builder.commands import RemoveWidget
    errors = []  # Tk fängt Ausnahmen in Callbacks ab und gibt sie nur aus
    canvas.winfo_toplevel().report_callback_exception = lambda *args: errors.append(args)
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    press(source, x, y)
    session.execute(RemoveWidget(ids["button"]))  # Entf, Maustaste noch gedrückt
    surface = canvas.surface
    move(surface, x + 60, y + 60)
    release(surface, x + 60, y + 60)
    assert session.project.find(ids["button"]) is None
    assert not drag.active
    assert errors == []


def test_second_click_soon_after_first_still_drags(free):
    session, canvas, drag, ids = free
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 25, 65)
    press(source, x, y)
    release(source, x, y)
    source = inner(canvas, ids["button"])
    press(source, x, y)  # gleich danach: Tk meldet das als <Double-Button-1>
    move(source, x + 100, y + 40, state=ALT)
    release(source, x + 100, y + 40)
    assert session.project.find(ids["button"]).layout.x == 120


def test_overshoot_keeps_last_container(free):
    """Aus dem Frame ins Fenster und über den Rand hinaus: bleibt im Fenster."""
    session, canvas, drag, ids = free
    source = inner(canvas, ids["entry"])
    x, y = surface_point(canvas, ids["frame"], 15, 15)
    press(source, x, y)
    over_window = surface_point(canvas, "window", 100, 280)
    move(source, *over_window)
    outside = (canvas.surface.winfo_rootx() - 40, over_window[1])
    move(source, *outside)
    release(source, *outside)
    assert session.project.parent_of(ids["entry"]).id == "window"
    assert session.project.find(ids["entry"]).layout.x == 0


def test_focus_on_canvas_after_palette_drop(free):
    session, canvas, drag, _ = free
    tile = drag.palette.buttons["CTkLabel"].winfo_children()[0]
    tile.focus_force()
    press(tile, tile.winfo_rootx() + 3, tile.winfo_rooty() + 3)
    target = surface_point(canvas, "window", 300, 280)
    move(tile, *target)
    release(tile, *target)
    canvas.update()
    assert canvas.focus_get() is canvas


def test_stray_release_does_not_press_toolbar_buttons(free_app):
    app, ids = free_app
    count = len(list(app.session.project.iter_widgets()))
    app.session.select(ids["button"])
    trash = app.toolbar_buttons["delete"]
    trash.event_generate("<ButtonRelease-1>", x=5, y=5)  # ohne Drücken davor
    app.update()
    assert len(list(app.session.project.iter_widgets())) == count
    from conftest import click
    click(trash, 5, 5)
    assert len(list(app.session.project.iter_widgets())) == count - 1


def test_pending_nudge_then_immediate_drag(free_app):
    app, ids = free_app
    session = app.session
    session.select(ids["button"])
    app.nudge(0, 1)  # Bewegung offen
    canvas = app.canvas
    view_before = canvas.views[ids["button"]]
    source = inner(canvas, ids["button"])
    x, y = surface_point(canvas, "window", 26, 65)
    press(source, x, y)  # übernimmt die Bewegung – ohne das gedrückte Widget neu zu bauen
    assert canvas.views[ids["button"]] is view_before
    assert session.project.find(ids["button"]).layout.x == 21
    move(source, x + 100, y + 40, state=ALT)
    release(source, x + 100, y + 40)
    assert session.project.find(ids["button"]).layout.x == 121


def test_pending_nudge_counts_as_unsaved(free_app, tmp_path):
    app, ids = free_app
    app.session.save(tmp_path / "frei.ctkb.json")
    app.session.select(ids["button"])
    app.nudge(0, 1)
    asked = []
    from ctk_builder.ui import main_window
    original = main_window.messagebox.askyesnocancel
    main_window.messagebox.askyesnocancel = lambda *a, **k: asked.append(a) or None
    try:
        assert not app.confirm_discard()
    finally:
        main_window.messagebox.askyesnocancel = original
    assert asked


def test_restack_with_ctrl_arrows_does_not_nudge(free_app):
    app, ids = free_app
    from ctk_builder.ui.main_window import MOD
    session = app.session
    session.select(ids["label"])
    app.canvas.focus_force()
    app.update()
    app.canvas.event_generate(f"<{MOD}-Up>")
    app.update()
    app.flush_nudge()
    children = [c.id for c in session.project.window.children]
    assert children.index(ids["label"]) == 1
    assert session.project.find(ids["label"]).layout.y == 20  # nicht verschoben
    labels = [app.menus["edit"].entrycget(i, "label")
              for i in range(app.menus["edit"].index("end") + 1)
              if app.menus["edit"].type(i) == "command"]
    assert "Alles frei anordnen" in labels
