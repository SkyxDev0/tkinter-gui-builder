from ctk_builder.geometry import Rect
from ctk_builder.snapping import MIN_SIZE, STEP, resize, snap_move

CONTAINER = (400, 300)


def test_snaps_to_step_without_neighbours():
    result = snap_move(Rect(37, 53, 100, 28), [], CONTAINER)
    assert (result.rect.x % STEP, result.rect.y % STEP) == (0, 0)
    assert (result.rect.width, result.rect.height) == (100, 28)


def test_aligns_left_edge_with_neighbour_and_shows_guide():
    other = Rect(43, 20, 120, 28)
    result = snap_move(Rect(46, 90, 100, 28), [other], CONTAINER)
    assert result.rect.x == 43
    guides = [g for g in result.guides if g.axis == "x"]
    # die Linie reicht vom Nachbarn bis zum verschobenen Widget
    assert any(g.position == 43 and g.start == 20 and g.end == result.rect.bottom
               for g in guides)


def test_aligns_centers_and_container_middle():
    # Mitte des Rechtecks (x + 50) liegt 3 px neben der Containermitte (200)
    result = snap_move(Rect(147, 101, 100, 28), [], CONTAINER)
    assert result.rect.x == 150
    assert any(g.axis == "x" and g.position == 200 and (g.start, g.end) == (0, 300)
               for g in result.guides)


def test_alignment_beats_grid_but_only_within_threshold():
    other = Rect(0, 0, 33, 10)  # rechte Kante 33
    near = snap_move(Rect(36, 100, 50, 20), [other], CONTAINER)
    assert near.rect.x == 33
    far = snap_move(Rect(45, 100, 50, 20), [other], CONTAINER)
    assert far.rect.x == 48  # nächstes 8-px-Raster


def test_disabled_keeps_exact_position():
    result = snap_move(Rect(37, 53, 100, 28), [Rect(40, 50, 10, 10)], CONTAINER, enabled=False)
    assert result.rect == Rect(37, 53, 100, 28)
    assert result.guides == ()


def test_resize_right_edge_snaps_and_left_stays():
    start = Rect(20, 20, 100, 28)
    other = Rect(0, 100, 203, 10)  # rechte Kante 203
    result = resize(start, "e", 81, 0, [other], (500, 300))  # Mitte 250 stört nicht
    assert result.rect == Rect(20, 20, 183, 28)
    assert any(g.axis == "x" and g.position == 203 for g in result.guides)


def test_resize_top_left_moves_origin():
    start = Rect(40, 40, 100, 40)
    result = resize(start, "nw", -9, -17, [], CONTAINER, enabled=False)
    assert result.rect == Rect(31, 23, 109, 57)


def test_resize_keeps_minimum_size_on_dragged_side():
    start = Rect(40, 40, 100, 40)
    shrunk = resize(start, "w", 500, 0, [], CONTAINER, enabled=False)
    assert shrunk.rect.width == MIN_SIZE and shrunk.rect.right == start.right
    flat = resize(start, "s", 0, -200, [], CONTAINER, enabled=False)
    assert flat.rect.height == MIN_SIZE and flat.rect.y == start.y


# ---------------------------------------------------------------- Plattform, HiDPI

import pytest  # noqa: E402

from ctk_builder import geometry  # noqa: E402
from ctk_builder.ui.drag_drop import snapping_enabled  # noqa: E402


@pytest.mark.parametrize("platform,alt,numlock", [
    ("linux", 0x8, 0x10),       # X11: Alt = Mod1, NumLock = Mod2
    ("darwin", 0x10, 0x0),      # macOS: Option = Mod2 (Cmd = Mod1 bleibt Einrasten)
    ("win32", 0x20000, 0x8),    # Windows: Alt eigenes Bit, NumLock = Mod1
])
def test_alt_disables_snapping_but_numlock_does_not(platform, alt, numlock):
    assert snapping_enabled(0x100 | numlock, platform)
    assert not snapping_enabled(0x100 | numlock | alt, platform)
    assert snapping_enabled("??", platform)  # manche Ereignisse liefern Text


@pytest.mark.parametrize("scaling", [1, 1.25, 1.5, 1.75, 2, 2.25])
def test_physical_logical_roundtrip_matches_ctk(scaling):
    for value in range(0, 2000):
        assert geometry.to_logical(geometry.to_physical(value, scaling), scaling) == value
    assert geometry.to_physical(7, 1.5) == 10  # wie CTk: int(7 * 1.5)
