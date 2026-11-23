export interface Scenario {
  calibration_hours: number;
  booking_utilization: number;
  already_automated: number;
  ai_speed_claim: number;
  ai_speed_interpretation: 'rate_increase' | 'time_reduction';
  scale_realization: number;
  monetizable_overlap: number;
  demand_hours_per_day: number;
  value_per_productive_hour: number;
  value_realization: number;
  value_mode?: 'additional_output' | 'fixed_output_savings';
  operating_days: number;
  discount_rate: number;
  contract_years: number;
  contract_total: number;
  replacement_due: boolean;
  rollout_months: number;
  fixed_overhead_us: number;
  baseline_gate_error: number;
  pulse_gate_error: number;
  baseline_gate_ns: number;
  pulse_duration_increase: number;
  t1_us: number;
  t2_us: number;
  n_qubits: number;
  layers: number;
  shots: number;
  seed: number;
  noise_mode: 'reported_total' | 'control_only';
  readout_error: number;
  [key: string]: number | string | boolean | undefined;
}

export type OptionId = 'baseline' | 'calibration' | 'pulse' | 'control';

export interface BenchmarkResult {
  p_success: number;
  ci_low: number;
  ci_high: number;
  shots: number;
  successes?: number;
  gate_count: number;
  layers?: number;
  n_qubits?: number;
  seed?: number;
  [key: string]: unknown;
}

export interface DecisionOption {
  id: OptionId;
  label: string;
  available_hours_day: number;
  booked_hours_day: number;
  recovered_hours_day: number;
  useful_hours_year: number;
  incremental_useful_hours_year: number;
  annual_benefit_usd: number;
  upfront_benefit_usd: number;
  customer_npv_usd: number;
  gross_value_pv_usd: number;
  break_even_value_per_hour_usd: number | null;
  [key: string]: unknown;
}

export interface AnalysisResponse {
  scenario: Scenario;
  benchmark: {
    baseline: BenchmarkResult;
    pulse: BenchmarkResult;
    throughput_ratio: number;
    baseline_cycle_us: number;
    pulse_cycle_us: number;
  };
  options: DecisionOption[];
  recommendation: {
    id: OptionId;
    title: string;
    summary: string;
    contract_verdict: string;
    price_ceiling_usd: number;
    initial_hypothesis: string;
    survived: boolean;
  };
  schedule: {
    baseline: { calibration: number; booked: number; idle: number };
    calibration: { calibration: number; booked: number; idle: number };
  };
  cashflows: { year: number; calibration: number; pulse: number; control: number }[];
  sensitivities: { parameter: string; label: string; low: number; high: number; low_npv: number; high_npv: number; option_id?: OptionId }[];
  heatmap: { value_per_hour: number; realization: number; winner: OptionId | 'none'; npv: number }[];
  depth_curve: { layers: number; baseline: number; pulse: number; baseline_low: number; baseline_high: number; pulse_low: number; pulse_high: number }[];
  assumptions: { key: string; label: string; value: unknown; kind: string; rationale: string }[];
  warnings: string[];
  evidence: {
    experiment_id: string;
    seed: number;
    shots: number;
    source: string;
    generated_at: string;
    [key: string]: unknown;
  };
}

export interface Snapshot {
  id: string;
  name: string;
  data: AnalysisResponse;
}
