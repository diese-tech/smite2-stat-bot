# GodForge Integration Guide

ForgeLens interoperates with GodForge, but GodForge is optional.

## Ownership Boundary

- GodForge owns draft/session flow, pick/ban flow, god claims, public draft embeds, JSON output, and draft-side helper commands.
- ForgeLens owns guild-scoped match records, active channel match context, wallets, wager lines, wagers, ledger transactions, payouts, refunds, official result confirmation, archive/export behavior, and stat/result tracking.
- GodForge is draft-only and never authoritative for results or economy settlement.

## Import Contract

- ForgeLens observes public embeds for a `ForgeLens Status` field.
- Supported keys are `draft_status`, `draft_id`, `forgelens_match_id`, `game_number`, and `draft_sequence`.
- ForgeLens imports JSON attachments only when `producer` is `GodForge`.
- Imports are idempotent on `source + guild_id + channel_id + draft_id + game_number`.

## Linking Rules

1. If `forgelens_match_id` is present, ForgeLens links the draft to that match.
2. Otherwise, if the channel has an active ForgeLens match context, ForgeLens links the draft to that match.
3. Otherwise, ForgeLens stores the draft as unlinked and keeps operating safely.

## Result And Economy Safety

- Draft completion can enrich a match with picks, bans, and selected gods.
- Draft completion never settles wagers.
- Settlement requires an official ForgeLens result through `/result`.
