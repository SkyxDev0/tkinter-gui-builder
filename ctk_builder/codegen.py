"""Erzeugt Python-Quelltext aus dem Projektmodell. Keine GUI-Abhängigkeit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ctk_builder.model import LineConfig, Node, Project, WidgetNode
from ctk_builder.widget_specs import GROUP, HANDLER, SPECS

HEADER = "# AUTOMATISCH GENERIERT von CTk Builder – nicht von Hand bearbeiten!"
MAX_LINE = 88


@dataclass(frozen=True)
class GeneratedFiles:
    ui_source: str
    logic_source: str


def _lit(value: Any) -> str:
    """Python-Literal mit doppelten Anführungszeichen für Strings."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def _call(indent: str, head: str, args: list[str]) -> list[str]:
    """head(args...) in eine Zeile, oder ein Argument pro Zeile, wenn zu lang."""
    one_line = f"{indent}{head}({', '.join(args)})"
    if len(one_line) <= MAX_LINE or not args:
        return [one_line]
    lines = [f"{indent}{head}("]
    lines += [f"{indent}    {arg}," for arg in args]
    lines.append(f"{indent})")
    return lines


def _line_config_args(config: LineConfig) -> list[str]:
    args = []
    if config.weight:
        args.append(f"weight={config.weight}")
    if config.minsize:
        args.append(f"minsize={config.minsize}")
    if config.uniform:
        args.append(f"uniform={_lit(config.uniform)}")
    return args


def _grid_config(indent: str, target: str, node: Node) -> list[str]:
    lines = []
    for axis, configs in (("row", node.grid.rows), ("column", node.grid.columns)):
        for index, config in enumerate(configs):
            args = _line_config_args(config)
            if args:
                lines += _call(indent, f"{target}.grid_{axis}configure", [str(index), *args])
    return lines


def _widget_args(widget: WidgetNode, master: str) -> list[str]:
    spec = SPECS[widget.type]
    args = [master]
    for prop in spec.props:
        value = widget.props.get(prop.name, prop.default)
        if prop.kind == GROUP:
            if value is not None:
                args.append(f"variable=self.{value}")
                value_prop = widget.props.get("value") or widget.name
                args.append(f"value={_lit(value_prop)}")
            continue
        if prop.name == "value":
            continue  # wird zusammen mit variable_group ausgegeben
        if value == prop.default:
            continue
        if prop.kind == HANDLER:
            args.append(f"{prop.name}=self.{value}")
        elif prop.name == "font_size":
            args.append(f"font=ctk.CTkFont(size={value})")
        else:
            args.append(f"{prop.name}={_lit(value)}")
    return args


def _grid_args(widget: WidgetNode) -> list[str]:
    layout = widget.layout
    args = [f"row={layout.row}", f"column={layout.column}"]
    if layout.rowspan != 1:
        args.append(f"rowspan={layout.rowspan}")
    if layout.columnspan != 1:
        args.append(f"columnspan={layout.columnspan}")
    if layout.padx:
        args.append(f"padx={layout.padx}")
    if layout.pady:
        args.append(f"pady={layout.pady}")
    if layout.sticky:
        args.append(f"sticky={_lit(layout.sticky)}")
    return args


def _widget_lines(widget: WidgetNode, master: str) -> list[str]:
    indent = " " * 8
    attr = f"self.{widget.name}"
    lines = _call(indent, f"{attr} = ctk.{widget.type}", _widget_args(widget, master))
    lines += _call(indent, f"{attr}.grid", _grid_args(widget))
    if widget.is_container:
        lines += _grid_config(indent, attr, widget)
    for child in widget.children:
        lines += _widget_lines(child, attr)
    return lines


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def handler_names(project: Project) -> list[str]:
    return _ordered_unique([w.props.get("command") for w in project.iter_widgets()])


def group_names(project: Project) -> list[str]:
    return _ordered_unique([w.props.get("variable_group") for w in project.iter_widgets()])


def generate_ui(project: Project, module_name: str) -> str:
    window = project.window
    indent = " " * 8
    out = [
        HEADER,
        f"# Eigene Logik gehört in {module_name}.py.",
        "import customtkinter as ctk",
        "",
        f"ctk.set_appearance_mode({_lit(window.appearance_mode)})",
        f"ctk.set_default_color_theme({_lit(window.color_theme)})",
        "",
        "",
        f"class {window.class_name}UI(ctk.CTk):",
        "    def __init__(self):",
        "        super().__init__()",
        f"        self.title({_lit(window.title)})",
        f"        self.geometry(\"{window.width}x{window.height}\")",
    ]
    if not window.resizable:
        out.append("        self.resizable(False, False)")
    out += _grid_config(indent, "self", window)

    groups = group_names(project)
    if groups:
        out.append("")
        out += [f"{indent}self.{g} = ctk.StringVar(value=\"\")" for g in groups]

    for child in window.children:
        out.append("")
        out += _widget_lines(child, "self")

    for handler in handler_names(project):
        out += [
            "",
            f"    def {handler}(self):",
            f"        raise NotImplementedError(\"{handler} in {module_name}.py implementieren\")",
        ]
    return "\n".join(out) + "\n"


def generate_logic(project: Project, module_name: str) -> str:
    cls = project.window.class_name
    out = [
        f"from {module_name}_ui import {cls}UI",
        "",
        "",
        f"class {cls}({cls}UI):",
    ]
    handlers = handler_names(project)
    if handlers:
        for i, handler in enumerate(handlers):
            if i:
                out.append("")
            out += [f"    def {handler}(self):", "        pass"]
    else:
        out.append("    pass")
    out += [
        "",
        "",
        'if __name__ == "__main__":',
        f"    app = {cls}()",
        "    app.mainloop()",
    ]
    return "\n".join(out) + "\n"


def generate(project: Project, module_name: str) -> GeneratedFiles:
    return GeneratedFiles(
        ui_source=generate_ui(project, module_name),
        logic_source=generate_logic(project, module_name),
    )
