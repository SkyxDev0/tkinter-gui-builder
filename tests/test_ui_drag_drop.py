import pytest

from conftest import grid_session, node_named
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.drag_drop import DragController, DropTarget, drop_target
from ctk_builder.ui.palette import Palette


@pytest.fixture
def drag(canvas):
    palette = Palette(canvas.master, canvas.session)
    palette.pack(side="left", before=canvas)
    canvas.update()
    return DragController(canvas, palette)


def below_grid(canvas):
    """Bildschirmposition knapp unter der letzten Zeile des Fensters."""
    surface = canvas.surface
    _, y, _, height = surface.grid_bbox(0, 3)
    return surface.winfo_rootx() + 10, surface.winfo_rooty() + y + height + 10


def drag_events(widget, to_x, to_y):
    widget.event_generate("<Button-1>", x=3, y=3,
                          rootx=widget.winfo_rootx() + 3, rooty=widget.winfo_rooty() + 3)
    widget.event_generate("<B1-Motion>", x=3, y=3, rootx=to_x, rooty=to_y)
    widget.event_generate("<ButtonRelease-1>", x=3, y=3, rootx=to_x, rooty=to_y)
    widget.update()


def test_drop_target_on_widget_and_beyond_grid(canvas):
    session = canvas.session
    save = node_named(session, "button_save")
    view = canvas.views[save.id]
    target = drop_target(canvas, view.winfo_rootx() + 5, view.winfo_rooty() + 5)
    assert target == DropTarget(node_named(session, "frame_buttons").id, 0, 1)
    assert drop_target(canvas, *below_grid(canvas)) == DropTarget("window", 4, 0)


def test_drop_target_skips_dragged_frame(canvas):
    frame = node_named(canvas.session, "frame_buttons")
    view = canvas.views[frame.id]
    target = drop_target(canvas, view.winfo_rootx() + 5, view.winfo_rooty() + 5,
                         moving=frame.id)
    assert target.container_id == "window"


def test_drag_from_palette_adds_at_drop_cell(drag):
    session = drag.session
    inner = drag.palette.buttons["CTkButton"].winfo_children()[0]
    drag_events(inner, *below_grid(drag.canvas))
    added = session.project.find(session.selected_id)
    assert added.type == "CTkButton"
    assert (added.layout.row, added.layout.column) == (4, 0)


def test_drag_widget_onto_other_swaps(drag):
    session = drag.session
    name = node_named(session, "label_name")
    mail = node_named(session, "label_mail")
    source = drag.canvas.views[name.id].winfo_children()[0]
    target = drag.canvas.views[mail.id]
    drag_events(source, target.winfo_rootx() + 3, target.winfo_rooty() + 3)
    assert session.project.find(name.id).layout.row == 1
    assert session.project.find(mail.id).layout.row == 0


def test_small_movement_is_a_click(drag):
    session = drag.session
    name = node_named(session, "label_name")
    source = drag.canvas.views[name.id].winfo_children()[0]
    drag_events(source, source.winfo_rootx() + 4, source.winfo_rooty() + 4)
    assert session.selected_id == name.id
    assert session.project.find(name.id).layout.row == 0


def test_drop_target_in_empty_window(root):
    session = grid_session()
    design = DesignCanvas(root, session)
    design.pack(fill="both", expand=True)
    root.update()
    surface = design.surface
    target = drop_target(design, surface.winfo_rootx() + 10, surface.winfo_rooty() + 10)
    assert target == DropTarget("window", 0, 0)
