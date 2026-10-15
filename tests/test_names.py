import pytest

from conftest import grid_project
from ctk_builder import names
from ctk_builder.model import Layout, WidgetNode


@pytest.fixture
def project():
    p = grid_project()
    p.window.children.append(WidgetNode(
        id="b", type="CTkButton", name="button_1",
        props={"command": "on_save"}, layout=Layout(),
    ))
    return p


@pytest.mark.parametrize("value", ["1abc", "mit leer", "class", "title", "_privat"])
def test_invalid_identifiers(project, value):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, value)


def test_widget_name_must_be_unique(project):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, "button_1")
    # der eigene Name ist erlaubt
    names.check_identifier(project, names.WIDGET, "button_1", node_id="b")


def test_handler_may_be_shared_but_not_clash_with_widget(project):
    names.check_identifier(project, names.HANDLER, "on_save")
    with pytest.raises(ValueError):
        names.check_identifier(project, names.HANDLER, "button_1")
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, "on_save")


def test_own_name_is_not_a_valid_handler(project):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.HANDLER, "button_1", node_id="b")
