# EVIDENCE/entire — Build-Process Checkpoints

Sponsor/tool: **Entire** — https://docs.entire.io · CLI `entire`

## Version

- **Entire CLI 0.10.5** (Go 1.26.6, darwin/arm64) — already present on PATH; verified against the
  current official documentation (docs.entire.io — Introduction, Installation, Quickstart;
  `entire --help` matches the documented command set: enable / agent / status / doctor /
  checkpoint list / agent-help, …).

## Exact verified setup commands (run 2026-10-10)

```bash
entire version                                   # Entire CLI 0.10.5
cd /Users/khushisarawagi/Desktop/factora-agents
entire enable -y --no-init-repo                  # repo already git-initialised
# → ✓ Installed hooks · ✓ Configured project (.entire/settings.json) · Ready.
entire status                                    # Enabled · branch main; agent hooks ready
entire doctor                                    # Git hooks OK; Codex hooks installed
```

Enabled **before** substantive product code was written, so the first checkpoint pairs the
scaffold session with the initial commit — the compliance story judges can verify.

## Initialisation status

| Check | Result |
|---|---|
| `entire status` | ✅ Enabled on branch `main` (re-verified at N1: "Checkpoints sync to: origin") |
| Git hooks | ✅ installed and OK per `entire doctor` |
| Codex-discovered hooks | ✅ installed; ⚠ trust approval pending (user action, below) |
| Checkpoints | ⏳ `entire checkpoint list` still shows **0 after the N1 commit** (verified 2026-10-10). Honest diagnosis: checkpoints materialise when Entire's commit hook runs *inside a supported agent session* (Claude Code / Codex / Cursor …). This workspace is driven by the Freebuff desktop app, whose commit flow does not currently trip Entire's post-commit session capture; Entire itself reports no failure (`doctor` clean). Capturing a real checkpoint needs either a session from one of the hooked agents or the `entire login` + Codex `/hooks` approval user actions below. Recorded per task rule §18: no checkpoint identifier is invented. Command to verify: `entire checkpoint list` |

## What artefact/checkpoint evidence we will capture later

- One checkpoint per build milestone (N1…), each linking the agent session — prompts, transcript,
  tool calls, changed files — to the milestone commit (`entire checkpoint list`).
- On demand: `entire search` across code + sessions; `entire recap` for a judge-facing summary;
  `entire activity` for the session timeline.
- Graph/search screenshots exported into this directory per submission checklist
  (`docs/EVIDENCE/entire/COMMANDS.md` will accumulate the commands actually run).

## User actions still required (recorded honestly, not blocking the build)

1. **Codex hook trust:** `entire doctor` reports 7 Codex-discovered hooks need approval —
   open Codex and run `/hooks` to approve them (or ignore if only Freebuff/Claude Code sessions
   are used; Entire still captures those).
2. **`entire login`:** current Entire authentication is stale ("Login for
   https://in.auth.entire.io is no longer valid"). Cloud features (mirroring, dashboard review,
   session upload) require `entire login`. Local checkpoint capture works without it; re-login
   when first publishing checkpoint evidence.
3. Optionally, after the GitHub remote is created: `entire repo mirror add` to also mirror the
   repository on Entire (see docs.entire.io/quickstart step 4).
