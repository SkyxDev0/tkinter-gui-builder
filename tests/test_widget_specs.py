import inspect

import customtkinter as ctk
import pytest

from ctk_builder.widget_specs import (
    CHOICE, COLOR, GROUP, HANDLER, INT, OPT_INT, OPT_STR, STR, SPECS, PropSpec,
    format_value, parse_value,
)

# Diese Eigenschaften werden von codegen besonders übersetzt
SPECIAL = {"font_size", "variable_group", "value"}


def test_all_v1_widgets_present():
    assert set(SPECS) == {
        "CTkLabel", "CTkButton", "CTkEntry", "CTkTextbox",
        "CTkCheckBox", "CTkSwitch", "CTkRadioButton", "CTkFrame",
    }
    assert [t for t, s in SPECS.items() if s.is_container] == ["CTkFrame"]


@pytest.mark.parametrize("widget_type", sorted(SPECS))
def test_defaults_match_customtkinter(widget_type):
    """Standardwerte müssen den echten CTk-Standardwerten entsprechen."""
    params = inspect.signature(getattr(ctk, widget_type).__init__).parameters
    for prop in SPECS[widget_type].props:
        if prop.name in SPECIAL:
            continue
        if prop.name in params:
            assert params[prop.name].default == prop.default, prop.name
        else:
            # wird über **kwargs an das tkinter-Widget durchgereicht
            assert "kwargs" in params, prop.name


def test_initial_values_are_known_props():
    for spec in SPECS.values():
        for key in spec.initial:
            spec.prop(key)


@pytest.mark.parametrize("kind,raw,expected", [
    (STR, " Hallo ", " Hallo "),
    (STR, "", ""),
    (OPT_STR, "", None),
    (OPT_STR, "x", "x"),
    (INT, "12", 12),
    (OPT_INT, "", None),
    (OPT_INT, " 3 ", 3),
    (COLOR, "", None),
    (COLOR, "#fff", "#fff"),
    (COLOR, "#1f6aa5", "#1f6aa5"),
    (COLOR, "transparent", "transparent"),
    (COLOR, "red", "red"),
    (HANDLER, "", None),
    (HANDLER, "on_save", "on_save"),
    (GROUP, "auswahl", "auswahl"),
])
def test_parse_value_valid(kind, raw, expected):
    assert parse_value(PropSpec("p", kind, None), raw) == expected


@pytest.mark.parametrize("kind,raw", [
    (INT, ""),
    (INT, "-1"),
    (INT, "1.5"),
    (OPT_INT, "abc"),
    (COLOR, "#12345"),
    (COLOR, "#ggg"),
    (HANDLER, "on save"),
    (GROUP, "1x"),
])
def test_parse_value_invalid(kind, raw):
    with pytest.raises(ValueError):
        parse_value(PropSpec("p", kind, None), raw)


def test_parse_choice():
    prop = PropSpec("state", CHOICE, "normal", ("normal", "disabled"))
    assert parse_value(prop, "disabled") == "disabled"
    with pytest.raises(ValueError):
        parse_value(prop, "kaputt")


def test_color_check_callback_can_reject_names():
    prop = PropSpec("c", COLOR, None)
    with pytest.raises(ValueError):
        parse_value(prop, "notacolor", color_check=lambda name: False)


def test_format_value():
    assert format_value(None) == ""
    assert format_value(12) == "12"
    assert format_value("x") == "x"
