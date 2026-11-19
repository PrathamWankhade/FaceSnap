import { test, expect } from '@playwright/test';
import {
  describeQualityIssues,
  parseEnrollmentQualityDetail,
  qualityMetricRows,
} from '../lib/enrollment';
import { consentStaleCopy, isConsentStale } from '../lib/consent';
import { challengeCopy } from '../lib/liveness';

/*
 * Pure-logic coverage for the signed-in-only UI added in Phase 1.
 *
 * A real signed-in session needs Firebase credentials, so the UI flows
 * themselves stay manual (docs/testing.md § Manual checklist) while the
 * mapping/copy helpers that drive them are exercised here in Node.
 */

test.describe('enrollment quality feedback', () => {
  test('rejects payloads that are not the structured quality detail', () => {
    expect(parseEnrollmentQualityDetail(undefined)).toBeNull();
    expect(parseEnrollmentQualityDetail('Photo is blurry')).toBeNull();
    expect(parseEnrollmentQualityDetail({ unrelated: true })).toBeNull();
  });

  test('maps backend sentences to deduplicated, actionable issues', () => {
    const detail = parseEnrollmentQualityDetail({
      message: 'Enrollment photo rejected.',
      reasons: [
        'Photo is blurry. Hold still and retake.',
        'Photo is too dark. Find better lighting.',
        'Photo is blurry. Hold still and retake.',
      ],
      metrics: { sharpness: 12.4, brightness: 30.1 },
      face_count: 1,
    });

    expect(detail).not.toBeNull();
    const issues = describeQualityIssues(detail!.reasons);
    expect(issues.map((issue) => issue.code)).toEqual(['blurry', 'too_dark']);
    for (const issue of issues) {
      expect(issue.title.length).toBeGreaterThan(0);
      expect(issue.fix.length).toBeGreaterThan(0);
    }
  });

  test('formats known metrics with units and skips null measurements', () => {
    const rows = qualityMetricRows({
      face_width: 180,
      brightness: 41.25,
      yaw_ratio: 0.06,
      roll_degrees: null,
    });

    expect(rows).toEqual([
      { key: 'face_width', label: 'Face width', value: '180 px' },
      { key: 'brightness', label: 'Brightness', value: '41.3 / 255' },
      { key: 'yaw_ratio', label: 'Yaw (0 = facing camera)', value: '0.060' },
    ]);
  });

  test('unknown rejection sentences still produce a retry instruction', () => {
    const [issue] = describeQualityIssues(['Something the UI has never seen.']);
    expect(issue.code).toBe('unknown');
    expect(issue.fix).toMatch(/retake/i);
  });
});

test.describe('consent gate logic', () => {
  test('stale when the recorded version differs from the notice', () => {
    expect(isConsentStale('2025-01', '2026-02')).toBe(true);
    expect(isConsentStale(null, '2026-02')).toBe(true);
  });

  test('not stale when versions match', () => {
    expect(isConsentStale('2026-02', '2026-02')).toBe(false);
  });

  test('an unavailable notice never blocks verification', () => {
    expect(isConsentStale('2025-01', null)).toBe(false);
    expect(isConsentStale('2025-01', undefined)).toBe(false);
  });

  test('copy names the previous and current versions', () => {
    const copy = consentStaleCopy('2025-01', '2026-02');
    expect(copy.title).toMatch(/consent/i);
    expect(copy.body).toContain('2025-01');
    expect(copy.body).toContain('2026-02');
  });
});

test.describe('liveness challenge copy', () => {
  test('known challenges have an instruction', () => {
    expect(challengeCopy('blink').title).toMatch(/blink/i);
    expect(challengeCopy('turn_left').instruction).toMatch(/left/i);
    expect(challengeCopy('turn_right').instruction).toMatch(/right/i);
  });

  test('an unknown challenge falls back to neutral guidance', () => {
    const copy = challengeCopy('some_future_challenge');
    expect(copy.title.length).toBeGreaterThan(0);
    expect(copy.instruction.length).toBeGreaterThan(0);
  });

  test('missing challenge text is still rendered', () => {
    expect(challengeCopy(null).title.length).toBeGreaterThan(0);
  });
});
