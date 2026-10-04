"""LIBRARY.EXE: books, chapters, notes, accent-insensitive search and private places."""

import pytest

from library import search, store


@pytest.fixture
def shelf(library_db):
    """A book with one public and one private chapter, each holding a note."""
    book = store.create_book("Προγραμματισμός")
    python = store.create_chapter(book["id"], "Python")
    secret = store.create_chapter(book["id"], "Ημερολόγιο", private=True)
    note = store.create_note(python["id"], "Λίστες", "Οι λίστες στην Python είναι mutable.", tags=["python"])
    store.create_note(secret["id"], "Σκέψεις", "Προσωπικές σημειώσεις για την Python.")
    return {"book": book, "python": python, "secret": secret, "note": note}


def test_normalize_strips_accents_and_case():
    # casefold also turns the final ς into σ, so word endings match however they're typed
    assert search.normalize("ΣΗΜΕΙΏΣΕΙΣ") == search.normalize("σημειώσεις") == "σημειωσεισ"


def test_find_ignores_accents_and_matches_prefixes(shelf):
    hits = store.find("ΛΙΣΤΕΣ")
    assert [h["title"] for h in hits] == ["Λίστες"]
    assert store.find("mutab")[0]["id"] == shelf["note"]["id"]  # prefix match


def test_private_notes_are_hidden_from_the_chat(shelf):
    everything = {h["title"] for h in store.find("python", match_all=False)}
    chat_view = {h["title"] for h in store.find("python", include_private=False, match_all=False)}
    assert everything == {"Λίστες", "Σκέψεις"}
    assert chat_view == {"Λίστες"}
    assert store.outline() == [{"book": "Προγραμματισμός", "chapters": ["Python (1)"]}]


def test_duplicate_book_titles_are_refused(shelf):
    with pytest.raises(store.Conflict):
        store.create_book("προγραμματισμος")  # same title, different accents and case


def test_save_to_creates_missing_places(library_db):
    note = store.save_to("Μαγειρική", "Γλυκά", "Κέικ", "Αλεύρι, αυγά, ζάχαρη.")
    assert note["created"] == ["book «Μαγειρική»", "chapter «Γλυκά»"]
    again = store.save_to("ΜΑΓΕΙΡΙΚΗ", "γλυκα", "Κουλουράκια", "Βούτυρο.")
    assert again["created"] == [] and again["chapter_id"] == note["chapter_id"]


def test_save_to_refuses_private_places_from_the_chat(shelf):
    with pytest.raises(store.Conflict):
        store.save_to("Προγραμματισμός", "Ημερολόγιο", "Νέα", "κείμενο")


def test_deleting_a_note_removes_it_from_search(shelf):
    store.delete_note(shelf["note"]["id"])
    assert store.find("λιστες") == []
    with pytest.raises(store.NotFound):
        store.get_note(shelf["note"]["id"])


def test_suggest_place_points_to_the_matching_chapter(shelf):
    place = store.suggest_place("Πώς ταξινομώ λίστες στην Python; Οι λίστες έχουν sort().")
    assert place is not None and place["chapter_id"] == shelf["python"]["id"]
