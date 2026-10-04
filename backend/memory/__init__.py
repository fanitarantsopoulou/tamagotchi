"""The pet's memory of its owner: short personal facts, grouped by category.

    "I'm a backend developer"  (work)      "Μαρία: my team lead"  (colleagues)
    "Watching Severance, season 2"  (shows & movies)

Facts are looked up on demand: the chat gets a `recall` tool and finds what's relevant to the
current message, instead of receiving everything every time. Facts marked private never reach
the chat at all.

Modules:
    store       SQLite storage (data/memory.db), categories and search
    chat_tools  recall / remember / update / forget tools and a short prompt section
    routes      the /api/memory endpoints for the MEMORY.EXE window
"""
