# ForgeLens

ForgeLens is a Discord bot for Smite 2 draft leagues. It helps league staff turn match screenshots and GodForge draft files into organized, reviewable season stats.

Players post screenshots. GodForge can post Draft JSON. ForgeLens reads the evidence, extracts stats with Gemini Vision, and writes everything into the league's Google Sheet.

ForgeLens is built to be **league-owned**. The league owner controls the Google account, Drive folder, credentials, and season sheets. The bot writes to that workspace; it does not require the developer to hold the league's data.

Originally built for **Frank's Retirement Home**, but designed to be adapted for other Smite 2 leagues.

---

## Who This Is For

ForgeLens is for leagues that want:

- a clean stat sheet without manually typing every scoreboard
- support for GodForge Draft JSON files
- a way to handle screenshots that players forget to label
- staff review before stats become official
- each Discord server's data kept separate
- league-owned Google Drive and Google Sheets data

Regular players mostly upload screenshots. Stat admins run the Discord commands.

---

## What ForgeLens Does

ForgeLens watches configured Discord channels and helps with the full match reporting flow:

1. A season is created with `/newseason`.
2. A match is created by GodForge JSON or by `/newmatch`.
3. Players upload scoreboard/details screenshots with the match ID.
4. ForgeLens sends screenshots to Gemini Vision for OCR.
5. Parsed stats are written to the active season sheet.
6. Low-confidence, partial, duplicate, or unlinked evidence is flagged for review.
7. A stat admin confirms the match result with `/result`.
8. Confirmed or official data can be used for reports and exports.

Screenshots and OCR are evidence. They do not make a match official by themselves.

---

## League-Owned Data

Each Discord server gets its own workspace:

- active season
- Google Sheet
- Drive folder
- match IDs
- evidence records
- stat rows
- stat admin configuration

The league owner should create and control the Google account, Cloud project, service account, Gemini API key, parent Drive folder, and generated season sheets.

If you hand this bot off to a league, they keep the keys and the data.

---

## Discord Usage Flow

### First-Time Season Setup

A stat admin runs:

```text
/newseason name:Season 1
```

ForgeLens creates a season folder and Google Sheet, then marks it as the active season for that Discord server.

### If The League Uses GodForge

1. GodForge posts the Draft JSON in the configured JSON channel.
2. Players upload screenshots in the screenshot channel and include the match ID.

Example player message:

```text
GF-08R8 scoreboard and details
```

3. Staff can check the match:

```text
/status uid:GF-08R8
```

4. If OCR needs another attempt, a stat admin replies to the screenshot and runs:

```text
/reparse
```

5. After review, a stat admin confirms the result:

```text
/result uid:GF-08R8 winner:Order score:2-1
```

### If The League Does Not Use GodForge

1. A stat admin creates a match ID:

```text
/newmatch blue_captain:Alice red_captain:Bob
```

2. ForgeLens replies with a match ID, such as:

```text
FRH-A1B2
```

3. Players include that match ID when uploading screenshots:

```text
FRH-A1B2 scoreboard and details
```

4. After review, a stat admin confirms the result:

```text
/result uid:FRH-A1B2 winner:Alice score:2-0
```

### If A Player Forgets The Match ID

ForgeLens saves the upload as unlinked evidence and alerts staff.

A stat admin replies to the screenshot message and runs:

```text
/link uid:GF-08R8
```

or:

```text
/link uid:FRH-A1B2
```

ForgeLens attaches the saved stats to that match.

---

## Slash Commands

| Command | Who Uses It | What It Does |
|---|---|---|
| `/newseason name:` | Stat admin | Creates a season Drive folder and Google Sheet, then makes it active |
| `/newmatch blue_captain: red_captain:` | Stat admin | Creates a match ID for leagues not using GodForge |
| `/status uid:` | Stat admin | Shows match status, game rows, stat rows, winner, and score |
| `/link uid:` | Stat admin | Reply-based command that attaches an unlinked screenshot to a match |
| `/reparse` | Stat admin | Reply-based command that sends screenshots through Gemini again |
| `/result uid: winner: score:` | Stat admin | Confirms the reviewed match result |

---

## Google Sheet Tabs

Each season gets a Google Sheet with these tabs:

| Tab | What It Contains |
|---|---|
| `Match Log` | Match IDs, captains, picks, bans, fearless pool, result, and lifecycle status |
| `Player Stats` | One row per player per game, with extracted stats and review status |
| `Unlinked` | Screenshots that were uploaded without a match ID |
| `Season Config` | Season metadata, active settings, and bot bookkeeping |
| `Evidence` | Screenshot/Draft JSON fingerprints used for duplicate protection |

ForgeLens adds `Guild ID` to persistent rows so different Discord servers do not share or overwrite each other's data.

---

## GodForge Boundary

GodForge owns live match orchestration:

- sessions
- drafts
- randomization
- picks and bans
- Draft JSON generation
- any current live/legacy betting or ledger behavior

ForgeLens consumes GodForge Draft JSON as optional match enrichment. Draft JSON can create or enrich a match shell, but it does not own stat values and does not make a match official.

Ledger and betting are not migrated into ForgeLens in this pass.

---

## Setup

Start with the full setup guide:

[SETUP.md](SETUP.md)

It walks through:

1. creating a league-owned Google account
2. creating a Google Cloud project
3. enabling Gemini, Sheets, and Drive APIs
4. creating a service account
5. filling in `.env`
6. testing Google/Gemini access
7. creating the shared parent Drive folder
8. deploying the bot

Do not run the bot for a real league until `test_auth.py` passes.

---

## Download Or Clone

Clone the repo:

```bash
git clone https://github.com/diese-tech/smite2-stat-bot.git
cd smite2-stat-bot
pip install -r requirements.txt
```

Or download the ZIP:

[Download ZIP](https://github.com/diese-tech/smite2-stat-bot/archive/refs/heads/main.zip)

---

## Important Docs

- [SETUP.md](SETUP.md): step-by-step setup for league owners/admins
- [CONTEXT.md](CONTEXT.md): product language, domain rules, and lifecycle definitions
- [MIGRATION_PLAN.md](MIGRATION_PLAN.md): ForgeLens hardening roadmap
- [docs/AI_WORKFLOW_GUARDRAILS.md](docs/AI_WORKFLOW_GUARDRAILS.md): required guardrails before AI-assisted code changes

Before implementation, debugging, migration, or production fix work, review the AI workflow guardrails.

---

## Current Tech Stack

| Area | Tool |
|---|---|
| Discord bot | `discord.py` |
| OCR / vision parsing | Google Gemini Vision |
| Season sheets | Google Sheets API |
| Season folders | Google Drive API |
| Auth | Google Cloud service account |
| Hosting | Railway recommended |
| Language | Python 3.12 |

---

## Current Status

ForgeLens is still an MVP, but it now supports guild-scoped seasons, matches, evidence, stat rows, and configuration. The main remaining hardening areas are deeper review tools, field-level confidence handling, better export commands, and eventual ledger planning if that responsibility moves out of GodForge later.
