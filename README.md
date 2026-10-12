# SchoolFlow Result Portal

A results-first portal for Nigerian nursery, primary and secondary schools. Teachers enter scores, reviewers approve them, and parents and students receive report cards that anyone can check with a QR code. Every step leaves an audit trail, so a published result can be trusted.

This repository holds the MVP: the "Audit-ready Result Trust Chain". It is a capstone project and is being built step by step, test first.

**Status:** Phase 4 (setup). The backend and frontend skeletons, CI and a staging site are in place; the product features come next.

## What it does (MVP)

- Schools are created by the platform; school admins create every other account. There is no public sign-up.
- Teachers enter scores (or skill ratings for nursery classes) on the sheets assigned to them.
- Results move through review and approval, then are published and never edited in place; corrections create a new revision with a reason.
- Report cards are generated as PDFs from the published record, with a QR code that leads to a public verification page.
- Parents see only their own children; students see only themselves.
- Schools pay per term by student count, in test mode for the MVP.

The full behaviour is in [`docs/SPEC.md`](docs/SPEC.md).

## How it is built

| Part | Technology |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.14) in a container |
| Database | PostgreSQL 17 with row-level security |
| Hosting | Vercel (one project, frontend and backend together) |
| Checks | GitHub Actions: secret scan, lint, types, tests, dependency audit, container smoke test |

Reasons for every choice are in [`DECISIONS.md`](DECISIONS.md). Commands for working on the code are in [`AGENT.md`](AGENT.md#stack-and-commands).

## Repository layout

```
backend/    FastAPI app and its tests
frontend/   Next.js app and its tests
design/     UI design handoff (tokens, screens, labels)
docs/       Specification, build plan and research
```

## Security

Secrets never go in this repository. Setting names are listed in `backend/.env.example` and `frontend/.env.example` with no values. Every commit is scanned for secrets, on the developer's machine and in CI. All data in tests, seeds and screenshots is fictional.

## Licence

Copyright (c) 2026 Chidimma Mogbo. All rights reserved.

The code is public so it can be read and reviewed. It is not open source: no permission is granted to copy, modify, distribute or use it without written permission from the author.
