# Campaign Manager — PF2e Edition

A self-hosted web app for Pathfinder 2e tabletop campaigns. Search spells, creatures, and feats; chat in real time with your group; track notes, references, events, and polls — all in one place.

Built for game masters and players who want a fast, local, Docker-ready tool without subscriptions or internet dependencies.

---

## Features

| Module | What it does |
|---|---|
| **Grimoire** | Search spells, feats, and items with full-text search. Hover to reveal French translation. |
| **Bestiaire** | Browse and search creatures from across PF2e sourcebooks. |
| **Chat** | Real-time WebSocket chatroom with dice rolls (`/roll 2d6`), coin flips, emotes, and image uploads. |
| **Polls** | Create polls directly in the chat. Votes update live for everyone. |
| **Calendar** | Schedule in-session events, track attendance per character. |
| **Notes** | Shared session notes with full CRUD, exportable to CSV. |
| **References** | Upload and share files (maps, handouts, tokens) within the group. |
| **Roll Tables** | Browse PF2e roll tables, roll directly in chat. |
| **Dual Theme** | Toggle between parchment (light) and cosmic horror (dark) — background changes each visit. |
| **Bilingual** | EN/FR toggle on Grimoire entries via language switcher. |

---

## Stack

- **Backend** — Python 3.12, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **Database** — SQLite (single file, persisted via Docker volume)
- **Frontend** — Vanilla JS, Jinja2 templates, CSS custom properties
- **Real-time** — WebSocket (FastAPI native)
- **Packages** — managed with [uv](https://github.com/astral-sh/uv)

---

## Quick Start (Docker)

```bash
docker compose up -d
```

Then open [http://localhost:5000](http://localhost:5000).

The database is automatically seeded on first run and persisted in a named volume (`cm_data`).

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `ADMIN_PASSWORD` | `bard1cus` | Password for the chat admin panel |
| `DB_PATH` | `/data/pf2e.db` | Override database path |

---

## Local Development

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/Bardicus-Kilgore/campaign-manager.git
cd campaign-manager

uv sync
.venv/bin/python -m uvicorn server:app --reload --port 5000
```

Open [http://localhost:5000](http://localhost:5000).

---

## Data & Content Notice

This app uses game data from **Pathfinder 2e** (Paizo Inc.), available under the [Open RPG Creative (ORC) License](https://paizo.com/orclicense). No copyrighted artwork is included. The PDFs and raw extraction files are not distributed with this repository — only the parsed game data (spell names, descriptions, creature stats) derived from ORC-licensed content.

> Not affiliated with or endorsed by Paizo Inc.

---

## Project Structure

```
campaign-manager/
├── server.py               # FastAPI entry point
├── app/
│   ├── database.py         # DB init + all queries
│   ├── router_pf2e.py      # Grimoire / Bestiary routes
│   └── router_chat.py      # Chat / WebSocket / REST API
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, background tiles
├── extraction/             # Scripts to build pf2e.db from PDFs
├── Dockerfile
└── docker-compose.yml
```

---

## License

MIT — do whatever you want with the app code. Game content belongs to its respective rights holders.
