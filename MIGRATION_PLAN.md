# GodForge to ForgeLens Migration Plan

This repo already contains the stat bot MVP: Discord commands, passive screenshot handling, Gemini Vision parsing, Google Sheets/Drive export, GodForge JSON support, and season/match commands. The migration goal is not a rewrite; it is a boundary hardening pass that moves stat/ledger responsibilities out of GodForge and into ForgeLens.

Current live boundary: GodForge owns draft/session orchestration and match handoff. ForgeLens owns the new guild-scoped community-points wager/ledger subsystem. Existing GodForge betting/ledger code is reference material only and should not be copied directly.

## Target boundary

### GodForge keeps

- God randomizer
- Session tracking
- Draft tracking
- 3-ban / 5-ban draft variations
- Pick/ban ownership
- Draft JSON generation
- Match ID handoff

### ForgeLens owns

- Screenshot intake
- Draft JSON intake
- OCR parsing
- Confidence scoring
- Review workflow
- Player identity mapping
- Match confirmation
- Google Sheets export
- Google Drive / OneDrive export
- Community-points wallets, wager lines, wagers, ledger transactions, payouts, refunds, and audit history

## MVP hardening sequence

### Phase 1 — Domain alignment

Add:

- `CONTEXT.md`
- `docs/adr/0001-separate-godforge-from-forgelens-responsibilities.md`
- `docs/adr/0002-scope-forgelens-data-by-discord-guild.md`
- `docs/adr/0003-use-separate-match-and-ledger-lifecycles.md`

Outcome:

- Future implementation work has clear language and boundaries.
- Claude/Codex sessions stop re-litigating what belongs in which bot.

### Phase 2 — Multi-guild configuration

Implement or verify:

- `guild_id` on every persistent record
- per-guild season config
- per-guild Google/Drive/OneDrive export settings
- stat admin users and roles
- confidence threshold config, default `90`
- betting enabled/disabled config, default `false`
- starting balance config, default `500`

The preferred deployment model remains league-owned: each guild/league owns its Google credentials, parent Drive folder, generated season sheets, and exported data.

Implemented or suggested commands:

```text
/forgelens setup
/forgelens config
/forgelens admin-add role: user:
/forgelens admin-remove role: user:
/forgelens confidence threshold:
/forgelens drive parent_drive_folder_id:
/forgelens prefix league_prefix:
/forgelens starting-balance amount:
/newseason name:
```

### Phase 3 — Match identity and dedupe

Implement or verify:

- Match ID uniqueness per guild
- duplicate alert when same `guild_id + match_id` receives another upload
- fuzzy matching for uploads without Match ID
- stats-only match creation when no match can be matched
- Draft JSON as optional enrichment

Suggested behavior:

```text
Has Match ID?
  yes:
    attach to existing match or create/import match shell
    alert if duplicate evidence looks suspicious
  no:
    fuzzy match by timestamp, player overlap, and teams
    attach if likely
    otherwise create stats-only match
```

### Phase 4 — OCR confidence and review

Implement or verify:

- field-level confidence scores
- auto-accept fields at or above 90%
- flag fields below 90%
- manual review before official status
- manual confirmation before ledger resolution

Important rule:

```text
High-confidence OCR does not equal official result.
```

### Phase 5 — Player identity model

Implement or verify:

```text
players
- player_id
- guild_id
- primary_ign
- discord_user_id nullable
- aliases_json
- active_status
```

Rules:

- stats attach to `player_id`
- Discord betting attaches to `discord_user_id`
- aliases resolve historical match data
- IGN changes must not split stat history

### Phase 6 - ForgeLens wager/ledger MVP

The first ForgeLens-owned wager/ledger MVP now exists, with settlement gated by official stat-admin match results.

Implemented MVP lifecycle:

```text
line_status:
created
open
closed
locked
settled
voided
archived
```

Rules:

- wallets are scoped by `guild_id + user_id`
- match outcome wagering comes first
- stat props come later
- ledger may only resolve after `match_status == official`
- payouts require stat admin settlement
- all balance changes write transactions
- community fantasy points only; no payment integration or real-money language

Implemented commands:

```text
/wager create
/wager open
/wager close
/wager lock
/wager void
/wager settle
/wallet check
/wallet adjust
/ledger post
/ledger transactions
/ledger audit
/ledger export
/ledger health
/bet
/wagers
/leaderboard
/help
```

Hardening still required:

- move economy state from JSON-on-volume to a database
- add a GodForge handoff signal for automatic line close/lock without letting GodForge settle wagers
- add CSV/Sheets export once JSON export has been live-validated

## Suggested implementation prompt

```text
You are working in the `diese-tech/smite2-stat-bot` repo.

Goal:
Harden the existing Smite 2 stat bot MVP into ForgeLens, a multi-guild stat tracking bot that owns evidence intake, OCR parsing, match confirmation, exports, and guild-scoped community-points wagering.

Read these docs first:
- CONTEXT.md
- docs/adr/0001-separate-godforge-from-forgelens-responsibilities.md
- docs/adr/0002-scope-forgelens-data-by-discord-guild.md
- docs/adr/0003-use-separate-match-and-ledger-lifecycles.md

Constraints:
- Do not rewrite the app from scratch.
- Preserve existing Gemini, Sheets, Drive, screenshot, JSON, and slash command behavior unless it conflicts with the docs.
- Scope all persistent data by `guild_id`.
- Treat Draft JSON as optional enrichment, not required input.
- Treat Google Sheets/Drive/OneDrive as export outputs, not the source of truth.
- Use a 90% default OCR confidence threshold.
- Require stat admin confirmation before official match status.
- Keep ledger/wager lifecycle separate from match status.
- Require official match status before wager settlement.
- Treat community points as fictional league points only.

Tasks:
1. Audit current code against the docs.
2. Identify records or services that are not guild-scoped.
3. Propose minimal schema/config changes.
4. Add or update setup/admin commands needed for multi-guild operation.
5. Add match lifecycle statuses.
6. Add duplicate handling for `guild_id + match_id`.
7. Add fuzzy dedupe for uploads without match ID.
8. Keep the economy subsystem service-layer first and avoid command-handler bloat.
9. Do not copy GodForge ledger code directly; use it only as historical reference.

Output:
- A concise implementation plan.
- Files to change.
- Risks.
- Step-by-step patch sequence.
```
