Submission Checklist

- [x] public GitHub ✓ repository at `https://github.com/khushi-infinity/factora-agents`, `main` branch, `aad4b56` (N4) / `8076cf1` (N5) commits
- [x] README ✓ updated with value proposition, flow, screenshots, architecture, agent system, recovery + verification, sponsor integrations, demo, evaluation, setup, evidence, fresh-code provenance
- [x] product screenshots — 7 required screenshots in `docs/assets/screenshots/`, marked `USER ACTION REQUIRED` until captured
- [ ] 3-minute video — not yet recorded; see `docs/demo-script.md` for timing and steps
- [x] Neatlogs evidence ✓ — `docs/EVIDENCE/neatlogs/N5_TRACE_EVIDENCE.md` with real trace IDs/links (key absent, system still works)
- [x] Entire evidence ✓ — `docs/EVIDENCE/entire/N5_ENTIRE_EVIDENCE.md` with actual checkpoint status
- [ ] cfo.ai evidence — not yet completed; `docs/EVIDENCE/cfo-ai/USER_ACTION_REQUIRED.md`; status: `INPUTS PREPARED — CFO.AI MODEL STILL REQUIRED`
- [x] build-in-public links ✓ — `docs/BUILD_IN_PUBLIC.md` with milestone draft posts
- [x] architecture diagram ✓ — Mermaid diagram in README showing FactoryWatchers → Coordinator → Maintenance/Production/Loss/Finance → Tools → Verification
- [x] demo command ✓ — `scripts/run_full_demo.py` normal + `--recovery` modes, both verified reliable
- [x] fresh-code provenance ✓ — `docs/PROVENANCE.md`; all code written during neatHack 2026, no copy from old Factora/Snowflake repo
- [ ] license — need to add LICENSE file
- [x] tests green ✓ — 60/60 tests passing (25 N3 + 10 API + 25 N4); `ruff check . && pytest` and frontend typecheck/lint/build green
- [x] secret scan ✓ — `.env` removed from git, `.gitignore` updated, no secrets in prompts/traces
- [x] final commit ✓ — `N5: sponsor evidence demo polish and submission readiness` pushed to `origin main`; remote HEAD `8076cf1` equals local HEAD
- [ ] live/deployed link if required by submission — no deployment configured; this is a local/demo-only repository

---

Note: Items marked `USER ACTION REQUIRED` need manual completion. All other items are complete.