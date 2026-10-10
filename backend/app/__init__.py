"""Factora backend (neatHack 2026 fresh implementation).

Layout (grows milestone by milestone; skeleton dirs exist from N0):
    app/api/      route modules - health now; world/twin/incidents/agents later
    app/agents/   the agent runtime + specialists (N3+) and tools/
    app/world/    deterministic factory simulation (N1+)
    app/ml/       fresh local ML (N2+)
    observability.py  the single neatlogs instrumentation point

All implementation code is written fresh during neatHack - see
docs/PROVENANCE.md.
"""

__version__ = "0.1.0"
