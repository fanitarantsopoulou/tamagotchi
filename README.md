# Smart Tamagotchi

Frontend: HTML/CSS/JS (`frontend/`) · Backend: Python + FastAPI (`backend/`)

## Run with Docker (recommended)

```bash
cd ~/Projects/tamagotchi
cp .env.example .env              # first time only, then paste your key into .env
docker compose up -d --build      # build & start in the background
```

Open http://localhost:8000. The container restarts by itself whenever Docker Desktop is running.

- After code changes: `docker compose up -d --build`
- Logs: `docker compose logs -f`
- Stop: `docker compose down`
- Pet data lives in `backend/data/` on the Mac (mounted into the container), so rebuilds don't reset it.

## Run locally (for development)

```bash
cd ~/Projects/tamagotchi
python3.12 -m venv .venv                            # first time only (needs Python 3.10+)
.venv/bin/pip install -r backend/requirements.txt   # first time only
cp .env.example .env                                # then paste your key into .env
cd backend && ../.venv/bin/uvicorn main:app --reload
```

Open http://localhost:8000

## Controls

- **A** (←): next icon · **B** (Enter): OK · **C** (Esc): back
- Icons: food, light/sleep, play, clean, stats, chat (opens the CHAT.EXE window), calendar (coming soon), "!" = needs attention

## Structure

- `backend/pet.py`: game logic (stats, decay over time, actions). Rates are constants at the top of the file.
- `backend/main.py`: API (`GET /api/pet`, `POST /api/pet/{feed|play|sleep|clean}`, `POST /api/reset`, `POST /api/chat`)
- `backend/chat.py`: AI chat with Claude (`claude-haiku-4-5`), replies in Greek; persona, live stats and closet go in the system prompt, plus tools to add/update/remove closet items
- `backend/closet.py`: reads/edits `backend/data/closet.json` (makeup & clothes)
- Voice: the chat's MIC button (speech-to-text) and spoken replies (text-to-speech) use the browser's built-in speech APIs, Greek (`el-GR`)
- `frontend/background.js`: draws the pixel-art wallpaper
- `backend/data/pet.json`: saved pet state
- `.env`: holds `ANTHROPIC_API_KEY` (git-ignored; template in `.env.example`)
  ![alt text](image.png)
