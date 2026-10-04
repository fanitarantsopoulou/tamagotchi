"""MEMORY.EXE: personal facts, their search and the private flag."""

import pytest


def test_add_cleans_text_and_labels_the_category(memory_db):
    m = memory_db.add("work", "  I'm a   backend developer ", subject="job")
    assert m["text"] == "I'm a backend developer" and m["category"] == "work"
    assert m["private"] is False and m["category_label"]


@pytest.mark.parametrize("category, text", [("pets", "a cat"), ("work", "   "), ("work", "x" * 501)])
def test_add_rejects_bad_input(memory_db, category, text):
    with pytest.raises(memory_db.Invalid):
        memory_db.add(category, text)


def test_search_finds_greek_words_without_accents(memory_db):
    memory_db.add("colleagues", "Η Μαρία είναι η team lead μου", subject="Μαρία")
    memory_db.add("watching", "Βλέπω Severance", subject="Severance")
    assert [m["subject"] for m in memory_db.search("μαρια")] == ["Μαρία"]


def test_private_facts_are_hidden_from_the_chat(memory_db):
    secret = memory_db.add("me", "A secret wish", private=True)
    assert memory_db.search("secret") == []
    assert memory_db.search("secret", include_private=True)[0]["id"] == secret["id"]
    with pytest.raises(memory_db.NotFound):
        memory_db.get(secret["id"], include_private=False)


def test_update_and_remove(memory_db):
    m = memory_db.add("likes", "Coffee")
    updated = memory_db.update(m["id"], text="Iced coffee")
    assert updated["text"] == "Iced coffee" and updated["category"] == "likes"
    memory_db.remove(m["id"])
    assert memory_db.all_memories() == []
    assert memory_db.search("coffee") == []
