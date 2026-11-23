import { describe, expect, it } from 'vitest';
import originalResults from '../../artifacts/scenarios.json';
import { catalogEntries, scenarioCatalog } from './catalog';

describe('precomputed evidence catalog', () => {
  it('exposes all eight actual saved analyses without changing their data', () => {
    expect(catalogEntries).toHaveLength(8);
    expect(new Set(catalogEntries.map((entry) => entry.id)).size).toBe(8);
    expect(catalogEntries.map((entry) => entry.id).sort()).toEqual(Object.keys(originalResults).sort());
    for (const entry of catalogEntries) {
      expect(scenarioCatalog[entry.id]).toEqual(originalResults[entry.id as keyof typeof originalResults]);
      expect(scenarioCatalog[entry.id].evidence.experiment_id).toMatch(/^qy-/);
    }
  });

  it('preserves the saved fixed-workload result and its distinct economic interpretation', () => {
    const saved = scenarioCatalog.same_work_savings;
    expect(saved.scenario.value_mode).toBe('fixed_output_savings');
    expect(saved.recommendation.contract_verdict).toBe('Renegotiate');
    expect(saved.options.find((option) => option.id === 'pulse')?.customer_npv_usd).toBeLessThan(0);
    expect(saved.benchmark.throughput_ratio).toBe(scenarioCatalog.case_default.benchmark.throughput_ratio);
  });
});
