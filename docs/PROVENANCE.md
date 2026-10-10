# PROVENANCE.md — Fresh-Code Disclosure (neatHack 2026)

**Rule context:** neatHack allows planning before the event, but the submitted code must be
written during the hackathon. This document states exactly what is old and what is new.

## What existed before neatHack

- **The Factora concept.** An operational digital twin for factory predictive maintenance existed
  as a prior project built for the Snowflake CoCo CLI Hackathon 2026 (GCC Edition).
- **The UI/UX design mockups.** Ten screen mockups (Command Center, Factory Digital Twin, Machines
  Explorer, Machine Detail, Predictive Maintenance, AI Maintenance Agent, Work Orders, Spare
  Parts, OEE & Production Analytics, Maintenance Planner & Reports) and their design language
  (navy sidebar, light content panels, blue accent, state colours green/amber/red/blue-gray/gray)
  existed before neatHack.
- **Architecture lessons.** Deterministic seeded data generation, honest model metrics with a model
  card, a documented demo-adapter pattern, and credential-free application boot are *ideas*
  carried forward.
- Old repository (reference only, public): https://github.com/khushi-infinity/Factora

## What this repository is

- **A brand-new Git repository** (`factora-agents`), initialised during neatHack 2026 with fresh
  Git history. It is not a branch, worktree, copy or fork of the old repository.
- **All submitted application code is written fresh during neatHack 2026**:
  - the FastAPI backend (`backend/`) — new implementation, new module layout;
  - the React frontend (`frontend/`) — new implementation, new components;
  - the factory simulation, agents, ML and tools (upcoming milestones) — all new code.
- **No old implementation source code was copied into this repository.** No old React components,
  FastAPI modules, ML code, data generators, tests, Snowflake files, or Playbook text were copied.

## What was deliberately carried over (permitted reference material)

- **`docs/design/mockups/*.jpg`** — the ten pre-existing mockup images, copied byte-identical as
  the visual design target. These are design reference images, not code. A sha256 spot-check
  confirms byte-identity with the source.
- **The rebuild plan** (`NEATHACK_REBUILD_PLAN.md`, kept in the reference repository) — a planning
  document produced by analysing the old project, used as the plan of record for this fresh build.
- **Ideas, not code** — e.g. "deterministic seeder with a fixed epoch", "honest holdout metrics",
  "demo adapter separated from evaluation" are conceptual references; reimplementations are new.

## What was explicitly retired

- All Snowflake / Cortex / CoCo CLI architecture, milestones and branding from the old project.
  The new Factora runs locally (FastAPI + SQLite + local simulation) with no Snowflake anywhere.
- The old 90-second single-agent demo story, replaced by a multi-agent
  observe → investigate → plan → act → verify → recover loop.

*Statement current as of milestone N0. Each later milestone's BUILD_LOG entry reaffirms that no
old repo code was consulted for copy purposes in that milestone.*
