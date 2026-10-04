"""File imports into the library: what's accepted and what's refused."""

import pytest

from library import importer


def test_markdown_import():
    result = importer.read("notes.md", "# Python\n\nLists are mutable.\n".encode())
    assert result.kind == "markdown"
    assert "Lists are mutable." in result.body


def test_text_import_handles_greek():
    result = importer.read("σημειώσεις.txt", "Καλημέρα κόσμε".encode("utf-8"))
    assert result.kind == "text" and result.body == "Καλημέρα κόσμε"


@pytest.mark.parametrize("name, data, message", [
    ("virus.exe", b"MZ", "Only"),
    ("empty.txt", b"   \n", "empty"),
    ("huge.txt", b"a" * (importer.MAX_TEXT_BYTES + 1), "too big"),
])
def test_rejected_files(name, data, message):
    with pytest.raises(importer.FileRejected, match=message):
        importer.read(name, data)


def test_path_in_the_filename_is_ignored():
    result = importer.read("../../etc/notes.md", b"# Title\n\nbody")
    assert result.body.endswith("body")
