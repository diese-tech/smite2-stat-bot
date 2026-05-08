# AI Workflow Guardrails

Review this document before implementation, debugging, refactoring, migrations, or production fixes in this repository.

## Core Rule

Move fast, but move surgically. Prefer the smallest safe change that solves the measured problem. Avoid broad rewrites, speculative refactors, or unrelated cleanup.

## Repo-Specific Focus

- Make OCR parsing and stat ingestion idempotent.
- Handle duplicate images and retries safely.
- Keep async worker behavior isolated and observable.
- Avoid synchronous fan-out during burst uploads.
- Plan safe season reset operations before changing season data flows.
- Minimize database pressure during high-volume screenshot ingestion.

## Required Before Changing Code

- Identify the specific problem and files likely involved.
- Name the expected impact and rollback path.
- Check whether the change affects ingestion, parsing, Google Sheets writes, Discord commands, data integrity, or production operations.
- Avoid touching unrelated files.

## Architecture Defaults

- Prefer queue-based async processing over synchronous fan-out.
- Prefer append-only raw ingestion records before derived stats.
- Prefer indexed match/image dedupe keys.
- Prefer bounded concurrency and explicit backoff.
- Prefer idempotent and retry-safe jobs.

## Change Review Checklist

Before finalizing a change, answer what changed, why it is safe, what could break, how to roll back, and what validation proves the change.
