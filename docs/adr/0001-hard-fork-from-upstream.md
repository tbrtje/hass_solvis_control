# Hard fork: support only one SolvisLeo 180, with no path back to upstream

This repository began as a fork of `LarsK1/hass_solvis_control`, a general-purpose
Solvis integration covering SC2 and SC3 controllers, fourteen tank configurations and
three heating circuits. We are narrowing it to the single installation it actually
runs on — one SolvisLeo 180 on SC3 — and severing the upstream relationship
completely: no further merges in either direction.

## Considered options

**Stay mergeable and narrow only at runtime.** The integration already polls just 72
of its 151 registers for this Anlage, so the generality costs almost nothing while
running. Rejected because the cost being paid is not runtime: it is the maintenance
and comprehension burden of tests, translations and documentation for thirteen tank
types and a controller generation we do not own.

**Contribute the general improvements upstream first, then diverge.** Rejected by the
owner. The work that is genuinely general — SolvisLeo support, block reads, coordinator
fault tolerance, version-register parsing — stays visible in the public fork, so
upstream can take it if it wants.

## Consequences

Upstream bug fixes will not arrive. In exchange, decisions that upstream cannot make
become available here: correcting register scaling that is wrong for this appliance,
deleting the SC2 code paths, and removing the configuration machinery that exists only
to tell devices apart.

The integration is renamed from `solvis_control` to `solvis_leo` so the two cannot be
confused or installed side by side. Entity history is not preserved across the rename;
the Anlage was three days old when this was decided, so there was nothing worth
keeping.
