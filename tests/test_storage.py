import os
import threading
import pytest
from unittest.mock import patch
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


def test_update_json_creates_when_missing(tmp_path):
    """update_json on a missing key passes None to the mutator and writes the result."""
    s = FileStorage(root=tmp_path)
    result = s.update_json("counter", lambda d: {"first": 1} if d is None else d)
    assert result == {"first": 1}
    assert s.read_json("counter") == {"first": 1}


def test_update_json_returns_mutated_value(tmp_path):
    s = FileStorage(root=tmp_path)
    s.write_json("counter", {"a": 1})
    result = s.update_json("counter", lambda d: {**d, "b": 2})
    assert result == {"a": 1, "b": 2}
    assert s.read_json("counter") == {"a": 1, "b": 2}


def test_update_json_is_atomic_under_concurrency(tmp_path):
    """Many threads concurrently appending different keys should all survive."""
    s = FileStorage(root=tmp_path)
    s.write_json("counter", {})

    def add(k):
        s.update_json("counter", lambda d: {**(d or {}), k: 1})

    threads = [threading.Thread(target=add, args=(f"k{i}",)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = s.read_json("counter")
    assert len(final) == 50
    assert all(final[f"k{i}"] == 1 for i in range(50))


def test_write_rolls_back_on_error_and_leaves_no_tmp(tmp_path):
    """If a write raises mid-flight, the original file is untouched and no .tmp leaks."""
    s = FileStorage(root=tmp_path)
    s.write("f", "original")

    # Make the inner write raise.
    real_fdopen = os.fdopen
    def boom(fd, *a, **kw):
        raise OSError("simulated mid-write failure")

    with patch("storage.os.fdopen", side_effect=boom):
        with pytest.raises(OSError):
            s.write("f", "new value that should not stick")

    # Original content preserved
    assert s.read("f") == "original"
    # No leftover tmp files
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_default_root_uses_data_dir_env(tmp_path, monkeypatch):
    """default_root() returns DATA_DIR if set, otherwise the project root."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from storage import default_root
    assert default_root() == tmp_path


def test_default_root_falls_back_to_project_root(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    from pathlib import Path
    from storage import default_root
    # Should be the salmon project root
    assert default_root() == Path(__file__).resolve().parent.parent
