import json

import pytest

from ctk_builder import project_io
from ctk_builder.project_io import FORMAT_VERSION, ProjectFileError


def test_roundtrip(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    project_io.save(kontakt, path)
    loaded = project_io.load(path)
    assert loaded.window == kontakt.window
    assert not (tmp_path / "kontakt.ctkb.json.tmp").exists()


def test_file_is_readable_json_with_version(tmp_path, kontakt):
    path = tmp_path / "k.ctkb.json"
    project_io.save(kontakt, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format_version"] == FORMAT_VERSION
    assert data["window"]["title"] == "Kontakt"


def write(tmp_path, content):
    path = tmp_path / "x.ctkb.json"
    path.write_text(content, encoding="utf-8")
    return path


def valid_data(kontakt):
    return project_io.to_dict(kontakt)


@pytest.mark.parametrize("content", ["", "{kaputt", "[]", "{}", '{"format_version": 1}'])
def test_broken_files(tmp_path, content):
    with pytest.raises(ProjectFileError):
        project_io.load(write(tmp_path, content))


def test_newer_version_is_rejected(tmp_path, kontakt):
    data = valid_data(kontakt)
    data["format_version"] = FORMAT_VERSION + 1
    with pytest.raises(ProjectFileError, match="neueren"):
        project_io.load(write(tmp_path, json.dumps(data)))


@pytest.mark.parametrize("mutate", [
    lambda w: w["children"][0].__setitem__("type", "CTkGibtsNicht"),
    lambda w: w["children"][0]["props"].__setitem__("unbekannt", 1),
    lambda w: w["children"][0].__setitem__("grid", {"rows": [{}], "columns": [{}]}),
    lambda w: w["children"][0]["layout"].__setitem__("farbe", "rot"),
    lambda w: w["grid"].__setitem__("rows", []),
    lambda w: w.pop("title"),
])
def test_invalid_content(tmp_path, kontakt, mutate):
    data = valid_data(kontakt)
    mutate(data["window"])
    with pytest.raises(ProjectFileError):
        project_io.load(write(tmp_path, json.dumps(data)))


def test_missing_file(tmp_path):
    with pytest.raises(ProjectFileError):
        project_io.load(tmp_path / "fehlt.ctkb.json")
