"""The library: a personal knowledge base shown as a bookshelf.

    books  ->  chapters (sub-topics)  ->  notes (title, Markdown text, tags, dates)

Modules:
    db          SQLite connection and schema (data/library.db, kept on the Docker volume)
    search      full-text search behind a small interface, so it can be swapped for a vector store
    store       create / read / update / delete for books, chapters and notes
    importer    turns uploaded .txt / .md / .pdf files into note text
    chat_tools  what the chat sees: a search tool, a save tool and a short prompt section
    routes      the /api/library HTTP endpoints

Privacy: everything stays in the local database. Books or chapters marked private are never
visible to the chat, and only the notes a search picks for a question are sent to the AI.
"""
