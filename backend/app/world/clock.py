"""Deterministic simulation clock.

The simulated factory runs on its own clock, decoupled from the wall clock:

  * `EPOCH` is the fixed initial simulation instant (never "now");
  * the current simulation time is persisted in the `world_state` table and
    survives restarts (plan §10: "persist or deterministically derive");
  * `advance()` moves the clock forward in whole simulation minutes;
  * rewinding/reset is a seed-time operation (reset_world() restores CLOCK to
    EPOCH inside the same transaction as the reseed).

All timestamps in the database are naive ISO strings representing plant-local
time — the demo story is scripted and does not need timezones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# Fixed initial simulation instant: a Monday 06:00 plant-local (after shift start).
EPOCH = datetime(2026, 10, 5, 6, 0, 0)

MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class Clock:
    """Immutable view of the simulation time; construct via Clock.from_iso()."""

    now: datetime

    @classmethod
    def at_epoch(cls) -> Clock:
        return cls(now=EPOCH)

    @classmethod
    def from_iso(cls, value: str) -> Clock:
        return cls(now=datetime.fromisoformat(value))

    @classmethod
    def load(cls, world_state: dict) -> Clock:
        raw = world_state.get("clock")
        return cls.from_iso(raw) if raw else cls.at_epoch()

    def iso(self) -> str:
        return self.now.isoformat(sep=" ", timespec="seconds")

    def plus_minutes(self, minutes: int) -> Clock:
        return Clock(now=self.now + timedelta(minutes=minutes))

    def iso_at(self, offset_minutes: int) -> str:
        """Timestamp `offset_minutes` from the current sim time (for telemetry rows)."""
        return (self.now + timedelta(minutes=offset_minutes)).isoformat(
            sep=" ", timespec="seconds"
        )

    def is_before_epoch(self) -> bool:
        return self.now < EPOCH
