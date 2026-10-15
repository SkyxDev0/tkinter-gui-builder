from conftest import grid_session
from ctk_builder.commands import AddWidget
from ctk_builder.ui.structure_tree import StructureTree


def test_tree_mirrors_model_and_selection(root):
    session = grid_session()
    tree = StructureTree(root, session)
    tree.pack()
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    label = AddWidget(frame.node_id, "CTkLabel")
    session.execute(label)
    assert tree.tree.get_children("window") == (frame.node_id,)
    assert tree.tree.get_children(frame.node_id) == (label.node_id,)
    assert "label_1" in tree.tree.item(label.node_id, "text")

    session.select(label.node_id)
    assert tree.tree.selection() == (label.node_id,)

    tree.tree.selection_set(frame.node_id)
    root.update()  # <<TreeviewSelect>> wird verzögert ausgelöst
    assert session.selected_id == frame.node_id
