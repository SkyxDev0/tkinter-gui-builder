from conftest import click, node_named
from ctk_builder.commands import AddWidget
from ctk_builder.ui.canvas import widget_kwargs


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
