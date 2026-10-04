"""Atomic JSON writes."""

import json

import storage


def test_write_json_creates_and_replaces(tmp_path):
    target = tmp_path / "nested" / "data.json"
    storage.write_json(target, {"a": 1})
    storage.write_json(target, {"name": "Μοχι"})
    assert json.loads(target.read_text()) == {"name": "Μοχι"}
    assert "Μοχι" in target.read_text()  # kept readable, not \\u-escaped


def test_write_json_leaves_no_temp_files(tmp_path):
    target = tmp_path / "data.json"
    storage.write_json(target, [1, 2, 3])
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_failed_write_keeps_the_old_file(tmp_path):
    target = tmp_path / "data.json"
    storage.write_json(target, {"ok": True})
    try:
        storage.write_json(target, {"bad": object()})  # not JSON-serializable
    except TypeError:
        pass
    assert json.loads(target.read_text()) == {"ok": True}
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]
