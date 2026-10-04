"""Shared fixtures: every test gets throwaway storage, so the real data in backend/data is never touched."""

import pytest


@pytest.fixture
def library_db(tmp_path, monkeypatch):
    """A fresh, empty library database for one test."""
    from library import db

    monkeypatch.setattr(db, "DB_FILE", tmp_path / "library.db")
    monkeypatch.setattr(db, "_initialized", False)  # create the schema in the new file
    return db


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """A fresh, empty memory database for one test."""
    from memory import store

    monkeypatch.setattr(store, "DB_FILE", tmp_path / "memory.db")
    monkeypatch.setattr(store, "_initialized", False)
    return store


@pytest.fixture
def reading_file(tmp_path, monkeypatch):
    """An empty reading shelf for one test."""
    from reading import store

    monkeypatch.setattr(store, "READING_FILE", tmp_path / "reading.json")
    return store
