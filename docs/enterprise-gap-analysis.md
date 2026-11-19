# Enterprise gap analysis

Status: living document (2026-11-17). Compares FaceSnap with enterprise FR/monitoring products —
NEC NeoFace, Amazon Rekognition, Azure Face, Hikvision/Dahua analytics, Genetec/Milestone VMS and
workforce T&A platforms (Kronos/UKG) — and records what is **implemented**, **partial**,
**planned** or **deliberately out of scope**.

Legend: ✅ implemented and tested · ◐ partial (say what is missing) · ○ planned (name the
prerequisite) · ✕ out of scope (see the reason/ADR).

This page exists to prevent two failure modes: claiming enterprise parity that does not exist, and
building surveillance features a single-campus attendance product should not have.

---

## A. Where FaceSnap is already strong

These are correctness properties, not marketing:

| Property | Evidence |
|---|---|
| Server-side match only; the browser never declares a match or writes attendance | NFR-C1, `docs/ARCHITECTURE.md`, `tests/test_permissions.py` |
| Database-enforced attendance idempotency | unique `(student_id, session_id)` + partial unique daily index, `tests/test_registry_api.py` |
| Multi-signal liveness (rPPG + blink + motion) with static-frame rejection | `app/services/liveness_service.py`, `tests/test_liveness.py` |
| Four capture modes (1:1, doorway batch, group upload, single stream) | `app/routes/`, frontend routes |
| DB-authoritative roles; fail-closed production guard | `app/auth.py`, `app/config.py`, `tests/test_security.py` |
| Biometric privacy: photo outside SQL, owner-only fetch, self-service deletion | `app/services/image_store.py`, `tests/test_permissions.py` |
| Audit trail, request ids, structured logs, readiness/liveness, metrics | `app/middleware/`, `app/metrics.py`, `docs/monitoring.md` |
| Migrations, ADRs, CI, Playwright, dependency audits | `.github/workflows/ci.yml`, `docs/decisions/`, `docs/testing.md` |

## B. Gaps, by category

### 1. Security & anti-spoofing

| Gap | Status | Reality / next step |
|---|---|---|
| Certified PAD (ISO/IEC 30107-3) | ✕ | Explicit non-goal: certification needs a certified lab, a spoof corpus and money. Liveness stays best-effort and is never described as certified. |
| Deepfake / virtual-camera / injection-attack detection | ◐ | Best-effort static/replay-frame ratio check (`detect_injection`) rejects a burst of identical frames during liveness. It is not device attestation and not a measured deepfake defence. |
| Active liveness (turn head / blink on command) | ◐ | Challenge-response protocol (`issue_challenge`/`verify_challenge`, `/api/liveness/challenge`, `/api/liveness/verify_challenge`) with single-use tokens, a 30 s TTL and a per-process cap. Wired into the student scan as an opt-in toggle; a failed challenge records no attendance. Passive remains the default and the thresholds are untuned against a spoof corpus. |
| Enrollment quality assessment (blur, pose, size, lighting) | ✅ | `face_service.assess_enrollment()` rejects blurry, tiny, dark, low-confidence, turned/tilted photos with machine-readable reasons; the register page turns the structured 422 into an actionable checklist plus the measured metrics. Tested in `tests/test_enrollment_quality.py`. |
| De-duplication / one face per identity | ✅ | Cosine distance ≤ `DUPLICATE_FACE_DISTANCE` (0.30) against the vector index blocks a second identity; audited. Requires Qdrant — the response exposes `duplicate_checked` rather than pretending. |
| Encryption at rest for photos/vectors | ◐ | The app does not encrypt files itself; reliance is on disk/volume encryption (KMS/HSM) at the host. Documented as a deployment responsibility, not a built-in claim. |

### 2. Recognition accuracy & robustness

| Gap | Status | Reality / next step |
|---|---|---|
| Published FAR/FRR/ROC benchmark | ◐ | Harness + protocol exist (`scripts/evaluate_recognition.py`, `docs/evaluation.md`); **no dataset run has been published**, so no number is claimed. |
| Demographic fairness testing | ○ | Needs a labelled, consented dataset with demographic metadata. Not possible with zero data; do not claim fairness. |
| Mask / occlusion-robust recognition | ○ | Pretrained ArcFace degrades with occlusion; no mask-aware model. Would need a vetted model + re-embedding (ADR). |
| IR / thermal / 3D face | ✕ | Requires different sensors and models; out of scope for a phone/webcam product. |
| Age / pose invariance validation | ◐ | The enrollment pose screen exists; invariance is not measured. Same dataset prerequisite as accuracy. |
| Ensemble / multi-model fusion | ✕ | One pretrained model (`buffalo_s`, ADR 0006). Fusion adds cost and calibration without a measured baseline. |

### 3. Monitoring & video analytics

| Gap | Status | Reality / next step |
|---|---|---|
| Multi-camera, RTSP/ONVIF, NVR federation | ◐ | Camera registry CRUD (`/api/cameras`, staff-only because stream URLs can carry RTSP credentials) with tests; per-camera RTSP workers and scheduler still planned. |
| Video analytics (counting, crowd density, zones, loitering) | ✕ | Different product (VMS analytics), different consent posture. See ADR 0002 and the non-goals in `docs/system-design.md`. |
| Real-time alerting (push/SMS/webhook) | ◐ | Webhook alerting added (`app/services/notifier.py`, `ALERT_WEBHOOK_URL`); fires on health degradation and error-rate spikes. Email/SMS still TODO. |
| PTZ control, camera health, auto-reconnect | ○ | Camera service exposes health; no PTZ/reconnect logic. Needs a device protocol layer. |
| Forensic face search over footage | ✕ | Would turn an attendance tool into surveillance; requires retention, legal basis and a separate access model. |
| Cross-camera re-identification | ✕ | Same reason as forensic search. |

### 4. Scale & performance

| Gap | Status | Reality / next step |
|---|---|---|
| Multi-node / millions of faces | ✕ | Single institution by design (ADR 0002). Postgres/Redis are supported for multi-worker hosts, but no capacity benchmark exists. |
| Distributed vector search | ◐ | Qdrant local mode is the default; a Qdrant server is configuration, not a deployed cluster. |
| GPU batching / throughput tuning | ○ | ONNX Runtime uses CUDA when available; no batching or throughput benchmark. |
| Edge / on-device inference | ○ | All inference is server-side. Edge would need a model-pack distribution and a sync protocol. |
| HA, auto-scaling, failover | ○ | No IaC, no load balancer, no staging. See `docs/hosting.md`. |
| CDN / edge caching | ✕ | Next.js static assets are cache-friendly, but the deployment target is local. Not a product gap. |

### 5. Integration & interoperability

| Gap | Status | Reality / next step |
|---|---|---|
| Enterprise SSO beyond Google (SAML/OIDC IdP, SCIM) | ○ | Firebase identity (Google) only; roles come from SQL. SAML/SCIM needs an IdP contract and a provisioning design. |
| HR/ERP/student-information-system sync | ◐ | `scripts/sync_students.py` (CSV idempotent upsert, dry-run) added. API-based sync still planned. |
| Access-control integration (door unlock, turnstile) | ✕ | Attendance is recorded, not an access-control panel. Physical control is a safety-critical integration and out of scope. |
| SIEM integration | ○ | Structured JSON logs + request ids exist; no Splunk/QRadar forwarder. A log shipper is deployment work. |
| Webhooks / event bus | ○ | No outbound events. Retention/attendance changes would be the first events. |
| API gateway / versioning policy | ◐ | Conventions exist (`docs/api-conventions.md`); no gateway or deprecation mechanism. |

### 6. ML lifecycle & model management

| Gap | Status | Reality / next step |
|---|---|---|
| Model versioning / rollback | ◐ | `model_version` column on students + payload; recorded at enroll/backfill; exposed in export and `/api/admin/model-info` (counts on old version). Rollback plan still an ADR away. |
| Drift detection | ◐ | Match-distance histogram added (`facesnap_match_distance_bucket` on /api/metrics). Alerting on drift threshold still TODO. |
| Retraining pipeline / human-in-the-loop labelling | ✕ | No training happens here (ADR 0006); a future model must arrive with a corpus, licence and evaluation report. |
| Model registry / shadow mode | ○ | Out of scope until there is a second model to compare. |

### 7. Compliance, governance & privacy

| Gap | Status | Reality / next step |
|---|---|---|
| Attendance retention-expiry job | ✅ | `scripts/purge_retention.py`, dry-run by default, positive-window guard, audited; tested in `tests/test_retention.py`. |
| Biometric retention / auto-expiry | ◐ | The **student** can delete photo + embedding + history; there is no automatic biometric expiry because that is an institutional policy decision (documented in `docs/consent.md`). |
| Data export (access/portability) | ✅ | `GET /api/students/{id}/export` (owner or staff, audited) returns profile, consent, attendance and a biometric note; tested. |
| Consent versioning / re-consent | ✅ | `consent_version` + `consent_at` columns, public `/api/consent`, enrollment rejects a stale version, and `ConsentGate` blocks the student scan until the current notice is accepted (`POST /api/consent/accept`, audited); migration included. |
| Privacy-preserving options (on-device, blurring non-enrolled faces) | ◐ | `app/services/anonymizer.py` can blur face regions in an image, but no export or stream path calls it yet. On-device inference does not exist. |
| SOC 2 / ISO 27001 / ISO 27701 alignment | ✕ | No certification or audit. Do not imply one. |
| BIPA/CCPA-specific handling | ◐ | Consent, deletion and export are implemented; state-specific notice/retention rules need counsel. |
| Immutable audit / chain of custody | ◐ | `audit_log` rows are append-only by convention, but a DB admin can mutate them. True immutability needs an append-only sink/hash chain. |

### 8. Product & UX

| Gap | Status | Reality / next step |
|---|---|---|
| Mobile native apps | ✕ | Responsive web only; a native app adds distribution and camera-permission work without changing the protocol. |
| Visitor management / watchlists | ✕ | Explicitly surveillance-adjacent; out of scope. |
| Shift/overtime/payroll (T&A beyond marking) | ✕ | Different product (workforce management). |
| Executive dashboards / scheduled reports | ◐ | `/api/analytics/overview` and `/api/analytics/trends` feed a staff-only `/analytics` page (overview cards, method breakdown, 30-day daily trend). CSV export via `/api/reports/attendance`. Scheduled/BI layer still TODO. |
| Case management for unmatched faces | ◐ | Review queue (`/api/detections/review`) with list/resolve/assign/bulk-resolve/bulk-dismiss, priority and category. There is no case history or per-reviewer audit view yet. |
| WCAG certification / i18n | ◐ | No certification and no translations. An automated axe gate (`frontend/e2e/a11y.spec.ts`) fails CI on critical/serious WCAG A/AA findings for public pages; signed-in pages are manual. Certification would need a human audit. |
| Offline-first | ✕ | Fails closed on connectivity loss; offline conflict resolution is a large design surface. |
| Mask/temperature screening | ✕ | Pandemic-era feature, no sensor, no consent basis. |

### 9. Operational maturity

| Gap | Status | Reality / next step |
|---|---|---|
| Staging environment / deploy pipeline | ○ | Compose + Dockerfiles exist; no hosted staging. `docs/hosting.md` describes what a host must provide. |
| Tested backup/restore | ◐ | SQLite backup/restore is implemented and tested (`app/services/backup.py`, `tests/test_backup_restore.py`); Postgres uses `pg_dump` and the quarterly drill in `docs/runbooks/backup-restore.md` is still manual. |
| Published SLOs / latency targets | ○ | Metrics exist; no SLO is claimed until a representative deployment is measured. |
| Chaos / failure injection | ○ | Health and fail-closed paths are tested; no fault-injection suite. |
| Blue-green / canary | ○ | Needs a real deployment target first. |
| Dependency vulnerabilities | ✅ | Backend `pip-audit --local` is green after removing unused Pillow; frontend `npm audit` reports **0 vulnerabilities** after removing unused `firebase-tools` and overriding patched transitive versions. |

## C. Prioritised roadmap

### P0 — before a campus pilot

1. **Certified/evaluated liveness** — at minimum, run a spoof-corpus evaluation and publish APCER/
   BPCER the way `docs/evaluation.md` publishes FAR/FRR. Certification stays out of scope.
2. **Benchmark accuracy** — the harness exists; a named, licensed dataset and a published report do
   not. This is a data/procurement task, not a coding task.
3. **Compliance lifecycle** — ✅ consent versioning, ✅ export, ✅ attendance retention, ✅ backup/
   restore mechanism. Remaining: institutional biometric-retention policy and a re-consent report.
4. **Production topology** — Postgres + Redis + a Qdrant server, `AUTO_MIGRATE=false` with a
   migration step, tested restore. Configuration exists; a real environment does not.
5. **Enrollment quality + duplicate guard** — ✅ implemented and tested.

### P1 — needed for a real deployment

6. Multi-camera / RTSP-ONVIF support with per-camera health.
7. Real-time alerting (webhook first, then email/SMS).
8. SAML/OIDC SSO + SCIM (requires an enterprise IdP contract).
9. Mask-aware recognition (model swap + re-embedding ADR).
10. Model versioning, drift histogram, rollback plan.
11. Scheduled/executive reporting.
12. Review queue for unmatched detections.

### P2 — competitive, later

13. Video analytics, forensic search, cross-camera re-ID — **only if the product changes** from
    attendance to surveillance, with a new consent/legal basis.
14. Edge inference, multi-modal biometrics, native mobile apps, visitor management.

## D. Deliberately not chasing

- **Billions-of-faces / distributed GPU clusters** — single institution (ADR 0002). Revisit only
  with a multi-tenant product decision.
- **Certified PAD Level 3 / government-grade** — airports/borders are a different market.
- **Multi-tenant SaaS / billing** — excluded by ADRs 0002 and 0003.
- **A full VMS (Genetec/Milestone parity)** — FaceSnap is attendance, not surveillance.

## Bottom line

The engineering core (server-side match, idempotency, fail-closed auth, audit, privacy, migrations,
CI) is at or above many commercial products. The honest distance to enterprise parity is
**(a) measured accuracy and liveness, (b) a biometric-retention policy, (c) multi-camera and
alerting, (d) enterprise integrations, and (e) a real production environment**. Items (a) and (b)
are evidence/policy work; (c)–(e) are scoped projects. None of them are fixed by adding a feature
list to the README.
