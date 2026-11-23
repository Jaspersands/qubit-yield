import type { AnalysisResponse, Scenario } from "./types";

export const optionNames: Record<string, string> = {
  baseline: "Keep current system",
  calibration: "AI calibration",
  pulse: "Pulse optimization",
  control: "Lower-cost controls",
  none: "Do not contract",
};

export const optionColors: Record<string, string> = {
  baseline: "#a5aaa4",
  calibration: "#98aeda",
  pulse: "#b3d46d",
  control: "#e7a68e",
  none: "#e7e5dc",
};

export function money(
  value: number | null | undefined,
  compact = true,
): string {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "Not reached";
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  if (compact && abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (compact && abs >= 1e3)
    return `${sign}$${(abs / 1e3).toFixed(abs >= 1e5 ? 0 : 1)}k`;
  return `${sign}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export const percent = (value: number, decimals = 1) =>
  `${(value * 100).toFixed(decimals)}%`;
export const number = (value: number, decimals = 0) =>
  value.toLocaleString("en-US", { maximumFractionDigits: decimals });

export const physicsKeys: (keyof Scenario)[] = [
  "baseline_gate_error",
  "pulse_gate_error",
  "baseline_gate_ns",
  "pulse_duration_increase",
  "t1_us",
  "t2_us",
  "n_qubits",
  "layers",
  "shots",
  "seed",
  "noise_mode",
  "readout_error",
];

export function physicsChanged(a: Scenario, b: Scenario): boolean {
  return physicsKeys.some((key) => a[key] !== b[key]);
}

export function applyPreset(current: Scenario, preset: string): Scenario {
  if (preset === "demand")
    return {
      ...current,
      demand_hours_per_day: 22,
      monetizable_overlap: 0.8,
      scale_realization: 0.9,
    };
  if (preset === "conservative")
    return {
      ...current,
      value_realization: 0.15,
      value_per_productive_hour: 500,
      rollout_months: 12,
      scale_realization: 0.4,
    };
  if (preset === "procurement") return { ...current, replacement_due: true };
  if (preset === "savings")
    return { ...current, value_mode: "fixed_output_savings" };
  if (preset === "optimistic")
    return {
      ...current,
      value_realization: 0.8,
      value_per_productive_hour: 2000,
      rollout_months: 3,
    };
  return current;
}

export function downloadFile(name: string, body: string, type: string) {
  const blob = new Blob([body], { type });
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export function analysisCsv(data: AnalysisResponse): string {
  const header = [
    "option",
    "annual_benefit_usd",
    "upfront_benefit_usd",
    "gross_value_pv_usd",
    "customer_npv_usd",
    "break_even_value_per_hour_usd",
  ];
  const rows = data.options.map((option) => [
    option.label,
    option.annual_benefit_usd,
    option.upfront_benefit_usd,
    option.gross_value_pv_usd,
    option.customer_npv_usd,
    option.break_even_value_per_hour_usd ?? "",
  ]);
  const safeCell = (cell: string | number) =>
    typeof cell === "string" && /^[\s]*[=+@-]/.test(cell) ? `'${cell}` : cell;
  return [header, ...rows]
    .map((row) =>
      row
        .map((raw) => {
          const cell = safeCell(raw);
          return `"${String(cell).replaceAll('"', '""')}"`;
        })
        .join(","),
    )
    .join("\n");
}

export async function apiRequest<T>(
  path: string,
  scenario?: Scenario,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  try {
    const response = await fetch(path, {
      signal: controller.signal,
      ...(scenario
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(scenario),
          }
        : {}),
    });
    if (!response.ok) {
      let detail = "";
      try {
        const body = await response.json();
        if (typeof body.detail === "string") detail = body.detail;
        else if (Array.isArray(body.detail))
          detail = body.detail
            .map(
              (x: { loc?: string[]; msg?: string }) =>
                `${x.loc?.slice(1).join(".") ?? "Input"}: ${x.msg ?? "Invalid value"}`,
            )
            .join("; ");
      } catch {
        /* Preserve the HTTP error if no JSON body exists. */
      }
      throw new Error(
        detail ||
          `The engine returned HTTP ${response.status}. Check the server and try again.`,
      );
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}
