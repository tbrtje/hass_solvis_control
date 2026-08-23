# Tolerate register failures at runtime instead of gating registers statically

The upstream integration decides which registers to poll from static configuration —
controller generation, tank type and a dozen feature options — and aborts the entire
poll cycle when any single register errors. With only one Anlage to support, all that
configuration collapses to constants, so the gating has nothing left to decide. It is
replaced by per-register fault tolerance: a failure on one register is logged and
skipped for that cycle, the rest of the cycle continues, and only a lost connection
fails the update as a whole. After three consecutive failures the affected entity goes
unavailable; a single success resets the count.

## Considered options

**Keep a learned skip list.** An earlier version remembered any address that answered
with ILLEGAL DATA ADDRESS and never asked again. Rejected: the list can go stale in a
way nothing detects. If the Wärmemengenzähler is switched on at the controller, a
register that was previously rejected starts working — but stays skipped until Home
Assistant restarts.

**Keep the static gating and add tolerance alongside it.** Rejected as redundant. With
one appliance the gating encodes knowledge that the device can simply be asked for, and
knowledge that has to be maintained by hand is knowledge that drifts.

## Consequences

A register the appliance does not implement costs one wasted request per cycle forever,
rather than one request in total. With this Anlage that is a handful of requests at
most, and it buys a system that repairs itself when the appliance changes underneath it.

This also removes the failure mode where one slow or dropped response takes every
entity in the integration unavailable — previously the common case, because transient
communication errors took the abort path while only the genuinely permanent error was
tolerated.
