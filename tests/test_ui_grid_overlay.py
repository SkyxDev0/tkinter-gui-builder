import pytest

from conftest import node_named
from ctk_builder.ui.grid_overlay import GridOverlay


@pytest.fixture
def overlay(canvas):
    grid_overlay = GridOverlay(canvas)
    canvas.update()  # Köpfe müssen sichtbar sein, bevor sie Klicks bekommen
    return grid_overlay


def test_draws_lines_for_every_container(overlay):
    # Fenster 4x2: 3 senkrechte + 5 waagerechte, Frame 1x2: 3 + 2
    assert len(overlay._lines) == 13


def test_headers_follow_active_container(overlay):
    # Fenster aktiv: 2 Spalten + 4 Zeilen + 2 Plus-Köpfe
    assert len(overlay._headers) == 8
    frame = node_named(overlay.session, "frame_buttons")
    overlay.session.select(frame.id)
    assert len(overlay._headers) == 2 + 1 + 2


def test_header_click_selects_line_and_plus_adds_column(overlay):
    session = overlay.session
    overlay._headers[0].event_generate("<Button-1>")
    assert session.selected_line == ("window", "column", 0)
    overlay.canvas.update()  # Köpfe wurden neu erzeugt und müssen erst sichtbar werden
    plus = next(h for h in overlay._headers if h.cget("text") == "+")
    plus.event_generate("<Button-1>")
    assert len(session.project.window.grid.columns) == 3
    assert len(overlay._lines) == 14  # eine senkrechte Linie mehr


def test_lines_can_be_hidden(overlay):
    overlay.set_lines_visible(False)
    assert overlay._lines == []
    assert len(overlay._headers) == 8  # Köpfe bleiben
    overlay.set_lines_visible(True)
    assert len(overlay._lines) == 13


def test_window_headers_sit_above_title_bar(overlay):
    canvas = overlay.canvas
    chrome_top = canvas.chrome.winfo_rooty() - canvas.winfo_rooty()
    column_header = overlay._headers[0]
    assert column_header.winfo_y() + column_header.winfo_height() <= chrome_top
