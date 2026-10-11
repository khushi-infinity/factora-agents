N5 Entire Evidence

CLI version: 0.11.4
Branch: main
Enabled: Yes (with some out-of-date hooks — run `entire enable --force` to refresh)
Checkpoints: 0 (no checkpoints saved on this branch yet)
Hook status: 7 Codex hook(s) need approval

Enabled agents:
- Agents · Claude Code, Codex, Copilot CLI, Cursor, Factory AI Droid, OpenCode, Pi
- Claude Code hooks out of date
- Copilot CLI hooks out of date

Git milestone chronology (supporting evidence):
- 1d0003c N2: interactive Factory Digital Twin and operational UI
- 838c1ad N3: autonomous maintenance incident response loop
- aad4b56 N4: coordinated production and financial optimisation

These commits represent the code provenance for N5 evidence.

Known Freebuff limitation:
- Checkpoints auto-save during agent sessions but require an active agent
- session to record. Run `entire agent-help` for machine-readable usage.
- No checkpoints exist until an agent session is active and recording.
- This is a CLI behavioral constraint, not a code bug.

Current supported commands only:
- `entire --version` — CLI version
- `entire status` — enabled agents, checkpoint count, hook status
- `entire checkpoint list` — list of saved checkpoints (currently empty)
- `entire agent-help` — machine-readable agent usage

No checkpoints remain 0 honestly — this is the true state after N4 commit.
Checkpoints will appear after subsequent agent sessions with recording enabled.

No fabrication of checkpoint IDs. The 0 checkpoint count is the recorded truth.