# ADR 0003: No billing layer

**Date:** 2026-10-23 · **Status:** Accepted

## Context

The SaaS playbook's commercial layers (plans, entitlements, metering, invoicing, dunning, tax)
only make sense once there is a paying customer and a price. FaceSnap has neither. Building them
would create:

- entitlement checks sprinkled through routes that currently express only *permissions*;
- a webhook surface (provider → app) that must be verified, retried and idempotent;
- failure modes (payment failed → attendance blocked?) that harm the actual users — students
  and staff — who never chose the payment system.

## Decision

**No billing, plans, quotas, entitlements, metering or invoicing.** Nothing in the product's
authorization model may be conditioned on a "plan". If a real adoption with a contract appears,
billing is an ADR-triggering decision and will be added at the edge (deployment/tenancy layer),
not inside attendance or recognition code.

## Consequences

- Authorization stays a pure function of role + ownership → testable in one table.
- No provider account, no webhook secrets, no dunning emails.
- The repo cannot be described as a "SaaS" in marketing copy — it is a system for institutions.
  Copy must say what it is.

## Alternatives considered

- **Feature-flag-gated "plans"** — invents commercial constraints with no customer.
- **Usage metering only, no charging** — still a schema, a retention policy and a UI nobody asked
  for; revisit when there is an actual capacity story.
