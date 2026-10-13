from conftest import click, node_named
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.canvas import EMPTY_LINE_MIN, DesignCanvas, widget_kwargs


def test_widget_kwargs_skip_defaults_and_code_only_props(canvas):
    button = node_named(canvas.session, "button_save")
    kwargs = widget_kwargs(button)
    assert kwargs["text"] == "Speichern"
    assert "command" not in kwargs
    assert "font" in kwargs
    radio = node_named(canvas.session, "radio_ja")
    assert "variable_group" not in widget_kwargs(radio)
    assert "value" not in widget_kwargs(radio)


def test_canvas_renders_every_widget(canvas):
    session = canvas.session
    assert set(canvas.views) == {w.id for w in session.project.iter_widgets()}
    entry = canvas.views[node_named(session, "entry_name").id]
    assert entry.grid_info()["column"] == 1
    assert int(canvas.surface.cget("width")) == 420


def test_click_selects_without_triggering_widget(canvas):
    session = canvas.session
    button = node_named(session, "button_save")
    click(canvas.views[button.id].winfo_children()[0])
    assert session.selected_id == button.id
    assert canvas._outline[0].winfo_ismapped()
    click(canvas.surface, x=410, y=250)  # leere Fläche unten rechts
    assert session.selected_id == "window"


def test_canvas_follows_model_changes(canvas):
    session = canvas.session
    command = AddWidget("window", "CTkSwitch")
    session.execute(command)
    canvas.update()
    assert command.node_id in canvas.views
    session.undo()
    canvas.update()
    assert command.node_id not in canvas.views


def test_node_at(canvas):
    session = canvas.session
    save = node_named(session, "button_save")
    view = canvas.views[save.id]
    assert canvas.node_at(view.winfo_rootx() + 5, view.winfo_rooty() + 5) == save.id
    surface = canvas.surface
    assert canvas.node_at(surface.winfo_rootx() + 410, surface.winfo_rooty() + 250) == "window"
    assert canvas.node_at(surface.winfo_rootx() - 10, surface.winfo_rooty() - 10) is None


def click_screen(canvas, x_root, y_root):
    """Klickt das Tk-Widget, das an der Bildschirmposition oben liegt – wie die echte Maus."""
    target = canvas.winfo_containing(x_root, y_root)
    click(target, x_root - target.winfo_rootx(), y_root - target.winfo_rooty())


def test_click_on_empty_area_of_frames_selects_them(canvas):
    """CTkFrame verbirgt sein internes Canvas in winfo_children(); Klicks darauf zählen trotzdem."""
    session = canvas.session
    command = AddWidget("window", "CTkFrame", 4, 0)
    session.execute(command)
    canvas.update()
    view = canvas.views[command.node_id]
    click_screen(canvas, view.winfo_rootx() + 20, view.winfo_rooty() + 20)
    assert session.selected_id == command.node_id
    surface = canvas.surface
    click_screen(canvas, surface.winfo_rootx() + 410, surface.winfo_rooty() + 250)
    assert session.selected_id == "window"


def test_empty_containers_have_measurable_cells(root):
    """Ohne Kinder berechnet Tk kein Raster; leere Zellen müssen trotzdem messbar sein."""
    session = Session()
    design = DesignCanvas(root, session)
    design.pack(fill="both", expand=True)
    root.update()
    assert design.surface.grid_bbox(0, 0) == (0, 0, EMPTY_LINE_MIN, EMPTY_LINE_MIN)
    frame = AddWidget("window", "CTkFrame", 0, 1)
    session.execute(frame)
    root.update()
    view = design.views[frame.node_id]
    assert view.grid_bbox(0, 0) == (0, 0, EMPTY_LINE_MIN, EMPTY_LINE_MIN)
    # der leere Frame behält seine Größe wie im echten Programm
    assert view.winfo_height() > EMPTY_LINE_MIN
