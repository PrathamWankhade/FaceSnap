# ADR 0002: Single institution — no multi-tenancy

**Date:** 2026-10-23 · **Status:** Accepted

## Context

The reference material for this phase (a 15-layer SaaS playbook) assumes a multi-tenant paid
product: organizations, tenant isolation, per-org feature flags, per-tenant quotas. Applying it
literally would mean:

- an `organization_id` (or `tenant_id`) on **every** table, query, permission check and test;
- org membership and invitation flows;
- row-level isolation guarantees with tests for cross-tenant reads;
- an admin model per org instead of three global roles.

FaceSnap serves **one institution**. There is no second customer, no invitation flow and no
org-scoped data anywhere in the product. Adding tenancy "because the playbook says so" would
roughly double the schema, the permission matrix and the test surface while delivering zero
user-visible value — and the isolation code would be untested against a real second tenant, i.e.
exactly the false-confidence failure mode the playbook warns about.

## Decision

FaceSnap is **single-institution**. We implement the *spirit* of tenancy as object-level
authorization (owner-or-staff checks, see [`../permissions.md`](../permissions.md)), not as
org scoping. Multi-tenancy is deferred until a real second institution is a committed product.

## Consequences

- Roles stay `admin` / `operator` / `student`, globally scoped and simple to test.
- Every list endpoint has exactly one isolation rule: staff see all, students see their own.
- A future multi-tenant version needs an ADR, a data backfill and a rewrite of
  `docs/permissions.md` — that is a known, accepted cost.

## Alternatives considered

- **Tenant column everywhere "for later"** — schema and queries become speculative; isolation
  with one tenant is untestable and therefore untrustworthy.
- **Separate databases per institution** — avoids the column, but breaks analytics, deploys and
  ops for a product with no second institution.
