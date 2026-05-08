import json
import pytest
from pathlib import Path
from storage import FileStorage


def test_write_then_read_text(tmp_path):
    s = FileStorage(root=tmp_path)
    s.write("greeting", "hello world")
    assert s.read("greeting") == "hello world"


def test_read_missing_returns_none(tmp_path):
    s = FileStorage(root=tmp_path)
    assert s.read("nope") is None


def test_write_then_read_json(tmp_path):
    s = FileStorage(root=tmp_path)
    s.write_json("data", {"x": 1, "y": [2, 3]})
    assert s.read_json("data") == {"x": 1, "y": [2, 3]}


def test_read_json_missing_returns_none(tmp_path):
    s = FileStorage(root=tmp_path)
    assert s.read_json("nope") is None


def test_write_is_atomic(tmp_path):
    """Writes should go through a temp file + os.replace so partial writes are impossible."""
    s = FileStorage(root=tmp_path)
    s.write("f", "first")
    s.write("f", "second")
    # No leftover *.tmp files in the storage dir
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
    assert s.read("f") == "second"


def test_special_keys_for_html(tmp_path):
    """report_html maps to report.html (not .report_html.json)."""
    s = FileStorage(root=tmp_path)
    s.write("report_html", "<html></html>")
    assert (tmp_path / "report.html").exists()
    assert s.read("report_html") == "<html></html>"
