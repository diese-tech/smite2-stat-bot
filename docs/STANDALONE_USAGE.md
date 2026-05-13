# Standalone ForgeLens Usage

ForgeLens works without GodForge installed.

## Match Lifecycle

1. Run `/match start` in the match channel and choose `Bo1`, `Bo3`, or `Bo5`.
2. Post screenshots in the configured screenshot channel as normal.
3. Use `/status` to inspect linked sheet rows and local match state.
4. Run `/result` when the outcome is official.
5. Settle or void wager lines only after the official result decision.

## Bo3 And Bo5 Workflow

- One ForgeLens `match_id` can contain multiple linked drafts.
- Each GodForge draft import is stored under that match by `game_number`.
- If GodForge is not present, the match still exists and results/economy still work.

## Ledger Behavior

- Ledger posts, audit history, transactions, and exports stay guild-scoped.
- Exports include linked draft metadata when present, but do not require it.
