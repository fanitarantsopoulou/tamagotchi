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
- Icons: top bar food, light/sleep, play, clean; bottom bar shows 4 at a time (stats, chat, outfits, mirror, calendar...) with ‹ › arrows to page through them

## Structure

- `backend/pet.py`: game logic (stats, decay over time, actions). Rates are constants at the top of the file.
- `backend/main.py`: API (`GET /api/pet`, `POST /api/pet/{feed|play|sleep|clean}`, `POST /api/reset`, `POST /api/chat`)
- `backend/chat.py`: AI chat with Claude (`claude-haiku-4-5`), replies in Greek; persona, live stats and closet go in the system prompt, plus tools to add/update/remove closet items
- `backend/theme.py`: visual themes. Before the normal chat, a small classifier call (structured JSON output: `is_theme_request`, `colors`, `motif`) detects requests like "βάλε κάτι χριστουγεννιάτικο"; the theme is saved in `backend/data/theme.json`. New motifs: add an entry to `PRESETS` (the prompt and schema are generated from it)
- `frontend/themes.js`: applies a theme via CSS variables (animated with `@property`), redraws the pixel wallpaper and adds per-motif LCD effects; motif decorations live in `MOTIFS`
- Outfits: the hanger icon opens OUTFITS.EXE to pick a preset by hand; every change plays a short "transformation" animation
- Mirror mode (`backend/mirror.py`, `backend/outfit_of_day.py`): the mirror icon opens MIRROR.EXE (live camera, front camera by default, FLIP to switch; file-input fallback). The photo is validated (JPEG/PNG/WEBP, max 10MB), shrunk to 1024px and compared by Claude vision with the outfit the pet suggested today (saved by the chat's `save_outfit_suggestion` tool); without a suggestion it comments freely. The verdict becomes a short mood reaction (happy / thinking / curious). Photos are never stored.
- Camera on the phone needs HTTPS: `tailscale serve --bg 8000` serves the app at `https://<mac-name>.<tailnet>.ts.net` with a Tailscale certificate (localhost works as-is on the Mac)
- `backend/closet.py`: reads/edits `backend/data/closet.json` (makeup & clothes)
- Voice: the chat's MIC button (speech-to-text) and spoken replies (text-to-speech) use the browser's built-in speech APIs, Greek (`el-GR`)
- `backend/data/pet.json`: saved pet state
- `.env`: holds `ANTHROPIC_API_KEY` (git-ignored; template in `.env.example`)
  ![alt text](image.png)
