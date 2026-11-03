# ADR 0001: Use ADRs

**Date:** 2026-10-23 · **Status:** Accepted

## Context

FaceSnap's shape changed several times (Firestore → SQL, "CCTV" → single-camera attendance,
prototype → hardened repo). Each change left reasoning only in commit messages and chat, so a
future contributor (human or agent) cannot tell *why* a rejected alternative is absent.

## Decision

Record every **irreversible or expensive-to-reverse** choice as an ADR in `docs/decisions/`,
numbered `NNNN-title.md`, with:

- **Status** — Proposed / Accepted / Superseded by ADR NNNN
- **Context** — the pressure we were under
- **Decision** — what we chose
- **Consequences** — including what we gave up

An ADR is required for: a new data store, a change to auth/permissions, a new third-party provider,
anything resembling tenancy or billing, a change to the biometric pipeline, and any new production
dependency that holds state.

## Consequences

- Small overhead per irreversible decision (~1 screen).
- The "why not" for rejected options (Firestore, multi-tenancy, billing) is preserved.
- Decisions are reviewable in a PR before the code lands.

## Alternatives considered

- **Wiki/confluence-style long-form design docs** — rot, and nobody updates them.
- **Only commit messages** — no rationale for rejected options, poor discoverability.
