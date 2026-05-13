# ForgeLens / Smite 2 Stat Bot Context

ForgeLens is a multi-server Smite 2 stat tracking Discord bot. It processes match evidence, normalizes player stats, exports league reports, and owns guild-scoped community-points wager and ledger workflows.

Current implementation boundary: GodForge owns drafts, sessions, pick/ban flow, and match handoff. ForgeLens owns wager lines, wallets, ledger transactions, payouts, result confirmation, and economy audit data. Existing GodForge betting/ledger code is reference material only and should not be copied blindly.

## Language

**ForgeLens**:
The stat tracking bot responsible for evidence intake, OCR parsing, normalized stat records, exports, and guild-scoped community-points ledger workflows.
_Avoid_: GodForge, draft bot, betting bot

**GodForge**:
The match orchestration bot responsible for sessions, drafts, god randomization, picks, bans, and optional draft JSON output.
_Avoid_: stat tracker, ledger owner

**Guild**:
A Discord server using ForgeLens as an isolated league workspace.
_Avoid_: global league, tenant when speaking to users

**League**:
The competitive community operating inside a Guild.
_Avoid_: server when discussing seasons, matches, standings, or staff workflow

**Season**:
A configured competitive period within a Guild used to group matches, exports, and reports.
_Avoid_: event, split unless the league explicitly uses that term

**Match**:
A Guild-scoped competitive game or set record created manually in ForgeLens or imported from GodForge.
_Avoid_: screenshot, upload, draft

**Match ID**:
The stable identifier used to attach draft JSON, screenshots, stats, exports, and optional ledger activity to a Match.
_Avoid_: UID when the context requires cross-system identity

**Draft JSON**:
A GodForge-generated evidence file containing picks, bans, selection order, and draft context.
_Avoid_: stat file, result file

**Evidence**:
Uploaded screenshots or Draft JSON used to support a Match record.
_Avoid_: proof when referring to raw files

**OCR Parse**:
A Gemini Vision extraction attempt that converts screenshot evidence into structured stat fields.
_Avoid_: final stats, confirmed result

**Confidence Score**:
The bot's estimate that an extracted OCR field is accurate.
_Avoid_: accuracy guarantee

**Review Required**:
A match state where low-confidence fields, duplicate signals, or conflicts require stat admin approval.
_Avoid_: failed, broken

**Confirmed Match**:
A match whose result and stat fields have been approved by a configured stat admin.
_Avoid_: parsed match

**Official Match**:
A confirmed match that is eligible for exports and, if enabled, ledger resolution.
_Avoid_: complete match

**Full Match**:
A match with both stat evidence and Draft JSON enrichment.
_Avoid_: official match

**Stats-Only Match**:
A match with stat evidence but no Draft JSON.
_Avoid_: incomplete match

**Player**:
A Guild-scoped Smite identity with a primary in-game name and optional Discord user mapping.
_Avoid_: Discord user when discussing stat history

**Primary IGN**:
The canonical Smite in-game name used for current player identity.
_Avoid_: username, display name

**Alias**:
A historical or alternate in-game name that resolves to a Player.
_Avoid_: duplicate player

**Stat Admin**:
A configured user or role allowed to review OCR, confirm matches, correct stats, and trigger exports.
_Avoid_: moderator unless the Discord role is literally a moderator

**Integration Owner**:
A server owner or authorized manager responsible for connecting export destinations and API credentials.
_Avoid_: bot owner

**Export**:
A generated output pushed to Google Sheets, Google Drive, OneDrive, or another configured destination.
_Avoid_: source of truth

**Ledger**:
The Guild-scoped community-points accounting module that tracks wallet balances, entries, outcomes, payouts, refunds, admin adjustments, and audit events.
_Avoid_: match record

**Bet**:
A Discord-user-scoped community-points wager attached to a ForgeLens wager line.
_Avoid_: real-money bet, payment, gambling product

## Relationships

- A **Guild** contains one or more **Seasons**.
- A **Season** contains many **Matches**.
- A **Match** belongs to exactly one **Guild**.
- A **Match** may have zero or one **Draft JSON** file.
- A **Match** may have many pieces of **Evidence**.
- A **Draft JSON** enriches a **Match** but does not own stat values.
- An **OCR Parse** is produced from screenshot **Evidence**.
- A **Confirmed Match** requires approval from a **Stat Admin**.
- An **Official Match** may be exported.
- A **Full Match** has both confirmed stats and draft context.
- A **Stats-Only Match** has confirmed stats without draft context.
- A **Player** belongs to exactly one **Guild**.
- A **Player** has one **Primary IGN** and may have many **Aliases**.
- A **Player** may be linked to zero or one Discord user.
- **Stats** attach to a **Player**.
- **Bets** attach to a Discord user.
- A **Ledger** belongs to one **Guild**.
- A **Ledger** may only resolve against an **Official Match**.
- GodForge may provide a Match ID or draft context, but ForgeLens owns wager state and settlement.

## Match lifecycle

ForgeLens tracks match/stat state separately from wager and ledger state.

### Match status

- `created`: Match shell exists.
- `evidence_uploaded`: Screenshots or Draft JSON have been attached.
- `parsed`: OCR has extracted structured stat fields.
- `review_required`: Low-confidence fields, duplicate evidence, or conflicts need review.
- `confirmed`: A stat admin approved the match result and stats.
- `official`: The match is eligible for exports and optional ledger resolution.
- `exported`: The match was pushed to configured external outputs.
- `archived`: The match is retained for history but no longer active.

### Wager line status

- `created`: A stat admin created a line, but bets are not open.
- `open`: Community-point wagers may be placed.
- `closed`: No new wagers may be placed.
- `locked`: The line is waiting for an official result or admin settlement.
- `settled`: Payouts are complete.
- `voided`: Bets were canceled or invalidated.
- `archived`: The line is retained for history.

## Validation rules

- OCR fields at or above the configured confidence threshold may be auto-accepted for draft-free stat processing.
- The default confidence threshold is 90%.
- Fields below the threshold require review.
- High-confidence OCR does not make a match official by itself.
- Any ledger payout requires official match status before resolution.
- Wagering uses fictional community fantasy points only. There is no real-money flow or payment integration.
- Duplicate uploads with the same Guild and Match ID must trigger an alert or review flow.
- Uploads without Match ID should use fuzzy deduplication before creating a new stats-only match.

## Example dialogue

> **Dev:** "If a server uploads only scoreboard screenshots, is that match invalid?"
> **Domain expert:** "No. That's a Stats-Only Match. It can still be parsed, reviewed, confirmed, and exported. It just lacks draft context."

> **Dev:** "Can the ledger resolve once OCR says the blue team won?"
> **Domain expert:** "No. OCR can suggest the result, but ledger resolution requires an Official Match confirmed by a Stat Admin."

> **Dev:** "Does GodForge own the match?"
> **Domain expert:** "GodForge may create the Match ID and Draft JSON, but ForgeLens owns the stat record and export workflow."

> **Dev:** "Does GodForge settle wagers?"
> **Domain expert:** "No. GodForge can hand off match context, but ForgeLens owns wager state, official-result settlement, payouts, and audit history."

## Flagged ambiguities

- "Stat Tracker" was too generic. Use **ForgeLens** or the repo name when referring to the stat bot.
- "Complete match" can mean stats parsed, draft enriched, confirmed, exported, or ledger-ready. Use lifecycle statuses instead.
- "Server owner" can mean Discord owner or league operator. Use **Integration Owner** for the person responsible for export credentials and destinations.
- "Player" can mean Discord user or Smite IGN. Resolved: stats are tied to Smite identity; betting is tied to Discord user.
