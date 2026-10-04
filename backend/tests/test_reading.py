"""MY♥SHELF: the reading-shelf store and its HTTP endpoints."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(reading_file):
    from reading import routes

    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


# ---------- store ----------
def test_add_trims_and_numbers_books(reading_file):
    a = reading_file.add("  Dune ", "Frank Herbert", "read", 5, "#AABBCC")
    b = reading_file.add("Circe")
    assert a == {"id": 1, "title": "Dune", "author": "Frank Herbert", "status": "read", "rating": 5, "color": "#aabbcc"}
    assert b["id"] == 2 and b["status"] == "read" and b["rating"] == 0


@pytest.mark.parametrize("kwargs, message", [
    ({"title": "   "}, "title"),
    ({"title": "X", "status": "lost"}, "Status"),
    ({"title": "X", "rating": 6}, "Rating"),
    ({"title": "X", "color": "pink"}, "Color"),
])
def test_add_rejects_bad_input(reading_file, kwargs, message):
    with pytest.raises(reading_file.ReadingError, match=message):
        reading_file.add(**kwargs)


def test_update_changes_only_given_fields(reading_file):
    book = reading_file.add("Dune", "Herbert", "shelf")
    updated = reading_file.update(book["id"], status="reading", color="")
    assert updated["title"] == "Dune" and updated["author"] == "Herbert"
    assert updated["status"] == "reading" and updated["color"] == ""


def test_update_and_delete_unknown_book(reading_file):
    with pytest.raises(reading_file.NotFound):
        reading_file.update(99, title="X")
    with pytest.raises(reading_file.NotFound):
        reading_file.delete(99)


def test_fill_adds_blank_books_only_once(reading_file):
    reading_file.add("Dune")
    shelf = reading_file.fill(3)
    titles = [b["title"] for b in shelf["books"]]
    assert titles == ["", "", "", "Dune"]  # blanks under the existing book
    assert shelf["filled"] is True
    assert len(reading_file.fill(3)["books"]) == 4  # a second fill does nothing


def test_deleted_blanks_stay_deleted(reading_file):
    blank = reading_file.fill(2)["books"][0]
    reading_file.delete(blank["id"])
    reading_file.fill(2)
    assert len(reading_file.shelf()["books"]) == 1


def test_reads_the_old_list_format(reading_file):
    reading_file.READING_FILE.write_text(json.dumps([{"id": 7, "title": "Old", "author": "", "status": "read", "rating": 2}]))
    shelf = reading_file.shelf()
    assert shelf["filled"] is False and shelf["books"][0]["title"] == "Old"
    assert reading_file.add("New")["id"] == 8


# ---------- HTTP ----------
def test_endpoints(client):
    assert client.get("/api/reading").json() == {"filled": False, "books": []}
    created = client.post("/api/reading", json={"title": "Dune", "rating": 4})
    assert created.status_code == 201
    book_id = created.json()["id"]
    assert client.patch(f"/api/reading/{book_id}", json={"status": "reading"}).json()["status"] == "reading"
    assert client.post("/api/reading/fill", json={"count": 2}).json()["filled"] is True
    assert client.delete(f"/api/reading/{book_id}").status_code == 204
    assert [b["title"] for b in client.get("/api/reading").json()["books"]] == ["", ""]


def test_endpoint_errors(client):
    assert client.post("/api/reading", json={"title": ""}).status_code == 400
    assert client.post("/api/reading", json={"title": "X", "status": "nope"}).status_code == 400
    assert client.patch("/api/reading/42", json={"title": "X"}).status_code == 404
    assert client.delete("/api/reading/42").status_code == 404
    assert client.post("/api/reading/fill", json={"count": -1}).status_code == 422
