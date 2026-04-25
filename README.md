# smite2-stat-bot

A standalone Discord bot for Smite 2 draft leagues. Watches your Discord channels for match screenshots and GodForge JSON draft files, extracts player stats using Google Gemini Vision AI, and automatically pushes clean data to a Google Sheet for staff to build reports from.

Built for **Frank's Retirement Home** — designed to be cloned and adapted for any Smite 2 draft league.

---

## Features

- **Passive screenshot parsing** — players post scoreboard + details screenshots, the bot extracts all stats automatically using Gemini Vision AI
- **Google Sheets integration** — stats push directly to a structured season sheet with no manual export
- **GodForge support** — automatically ingests draft JSON files (picks, bans, fearless pool) posted by GodForge
- **`/newmatch` for non-GodForge leagues** — staff generate match UIDs manually if GodForge isn't in use
- **Reaction system** — ✅ linked, ⚠️ partial/unlinked, ❓ unrecognized, ❌ failed
- **Unlinked tab** — screenshots posted without a match ID are saved for staff to resolve with `/link`
- **Staff slash commands** — `/status`, `/link`, `/result`, `/reparse`, `/newseason`, `/newmatch`
- **Per-season Drive folders** — each `/newseason` creates a nested folder inside a shared top-level Drive folder (share the folder with staff + the bot service account as Editor)

---

## Getting Started

### Option 1 — Clone the repo

```bash
git clone https://github.com/diese-tech/smite2-stat-bot.git
cd smite2-stat-bot
pip install -r requirements.txt
```

### Option 2 — Download ZIP

[Download ZIP](https://github.com/diese-tech/smite2-stat-bot/archive/refs/heads/main.zip) — extract and open the folder.

---

## Setup

Full setup instructions are in [SETUP.md](SETUP.md). It covers:

1. Creating a dedicated Google account
2. Setting up a Google Cloud project
3. Enabling the Gemini, Sheets, and Drive APIs
4. Creating a service account and downloading credentials
5. Filling in `.env`
6. Running `test_auth.py` to verify everything works
7. Creating the shared Drive folder (league owner, one-time)
8. Deploying to Railway for 24/7 uptime

**Do not run the bot until `test_auth.py` passes.**

---

## Adapting for Your League

1. Clone or download the repo
2. In `config.py`, update:
   ```python
   LEAGUE_NAME = "Your League Name"
   LEAGUE_SLUG = "your-league-name"
   ```
3. In `.env`, set `LEAGUE_PREFIX` to a 2–4 letter abbreviation (e.g. `OWL`, `TSL`). This is used by `/newmatch` to generate match UIDs.
4. Rename your credentials file to `your-league-name-credentials.json` and update `GOOGLE_CREDENTIALS_PATH` in `.env`.
5. Follow SETUP.md from Section 1.

If your league uses GodForge, the JSON drop channel and UID parsing work automatically. If not, staff use `/newmatch` to generate UIDs instead.

---

## Slash Commands

| Command | Who | Description |
|---|---|---|
| `/newmatch blue_captain: red_captain:` | Staff | Generate a match UID and log it to the sheet |
| `/status uid:` | Staff | Show game count and sheet status for a match |
| `/link uid:` | Staff | Reply-based — link an unlinked screenshot to a match ID |
| `/result uid: winner: score:` | Staff | Set the series result for a match |
| `/reparse` | Staff | Reply-based — re-send screenshots to Gemini for a fresh extraction |
| `/newseason name:` | Staff | Create a new season sheet and Drive folder, set as active |

---

## Google Sheets Structure

Each season gets its own spreadsheet with four tabs:

| Tab | Contents |
|---|---|
| **Match Log** | One row per game — draft ID, captains, picks, bans, fearless pool, result |
| **Player Stats** | One row per player per game — all extracted stats |
| **Unlinked** | Screenshots posted without a match ID — resolved by staff with `/link` |
| **Season Config** | Bot metadata — season name, game count, last updated |

---

## Tech Stack

| Component | Tool |
|---|---|
| Language | Python 3.12 |
| Discord | discord.py |
| Vision AI | Google Gemini 2.0 Flash |
| Spreadsheet | Google Sheets API |
| File storage | Google Drive API |
| Auth | Google Cloud Service Account |
| Hosting | Railway (recommended) |

---

## Project Structure

```
smite2-stat-bot/
├── bot.py                        # Discord client, event listeners
├── config.py                     # All settings and env vars
├── handlers/
│   ├── screenshot_handler.py     # Passive listener — images → Gemini → sheet
│   ├── json_handler.py           # GodForge JSON → Match Log
│   └── match_correlator.py       # Merges scoreboard + details extractions
├── commands/
│   ├── newmatch.py               # /newmatch
│   ├── status.py                 # /status
│   ├── link.py                   # /link
│   ├── result.py                 # /result
│   ├── reparse.py                # /reparse
│   └── newseason.py              # /newseason
├── services/
│   ├── gemini_vision.py          # Gemini API wrapper
│   └── sheets_service.py         # Google Sheets read/write
└── utils/
    └── uid_parser.py             # Extracts match UIDs from text and filenames
```

---

*Built for Frank's Retirement Home Smite 2 Draft League.*
