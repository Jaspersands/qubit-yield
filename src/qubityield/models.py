"""Validated, serializable scenario inputs for the QubitYield decision model.

Case observations and explicit analyst assumptions deliberately share one model:
every calculation can be reproduced from the exported scenario, rather than from
hidden dashboard defaults.  ``economics.assumptions_ledger`` identifies their
different evidentiary status.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .quantum import MAX_TRAJECTORY_GATE_UPDATES


class Scenario(BaseModel):
    """One decision scenario. Monetary inputs are nominal US dollars.

    ``booking_utilization`` records the original observed booking fraction.
    ``demand_hours_per_day`` is the operative demand scenario. Its default is
    70% of the original 16 available hours, so it can be varied independently to
    investigate a future backlog without rewriting the case observation.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)

    calibration_hours: float = Field(default=8.0, ge=0, le=24)
    booking_utilization: float = Field(default=0.70, ge=0, le=1)
    already_automated: float = Field(default=0.35, ge=0, le=1)
    ai_speed_claim: float = Field(default=0.70, ge=0, le=1)
    ai_speed_interpretation: Literal["rate_increase", "time_reduction"] = "rate_increase"
    scale_realization: float = Field(default=0.70, ge=0, le=1)
    monetizable_overlap: float = Field(default=0.25, ge=0, le=1)
    demand_hours_per_day: float = Field(default=11.2, ge=0, le=24)

    value_per_productive_hour: float = Field(default=1000.0, ge=0, le=1_000_000)
    value_realization: float = Field(default=0.35, ge=0, le=1)
    value_mode: Literal["additional_output", "fixed_output_savings"] = "additional_output"
    operating_days: int = Field(default=365, ge=1, le=366)
    discount_rate: float = Field(default=0.12, ge=0, le=1)
    contract_years: int = Field(default=3, ge=1, le=10)
    contract_total: float = Field(default=5_000_000.0, ge=0, le=1_000_000_000)
    rollout_months: float = Field(default=6.0, ge=0, le=120)

    replacement_due: bool = False
    control_cost: float = Field(default=2_000_000.0, ge=0, le=1_000_000_000)
    control_saving: float = Field(default=0.30, ge=0, le=1)
    control_engineers: int = Field(default=3, ge=0, le=100)
    control_integration_months: float = Field(default=6.0, ge=0, le=120)
    engineer_annual_cost: float = Field(default=300_000.0, ge=0, le=10_000_000)

    n_qubits: int = Field(default=20, ge=2, le=100)
    layers: int = Field(default=20, ge=2, le=100)
    shots: int = Field(default=8192, ge=256, le=65_536)
    seed: int = Field(default=7, ge=0, le=2**32 - 1)
    baseline_gate_error: float = Field(default=0.01, ge=0, le=0.20)
    pulse_gate_error: float = Field(default=0.005, ge=0, le=0.20)
    baseline_gate_ns: float = Field(default=300.0, gt=0, le=1_000_000)
    pulse_duration_increase: float = Field(default=0.40, ge=0, le=4)
    fixed_overhead_us: float = Field(default=100.0, ge=0, le=1_000_000)
    t1_us: float = Field(default=120.0, ge=0.001, le=1_000_000)
    t2_us: float = Field(default=120.0, ge=0.001, le=1_000_000)
    noise_mode: Literal["reported_total", "control_only"] = "reported_total"
    readout_error: float = Field(default=0.0, ge=0, le=0.50)

    @model_validator(mode="after")
    def validate_physical_structure(self) -> "Scenario":
        if self.n_qubits % 2:
            raise ValueError("n_qubits must be even for the disjoint-pair benchmark")
        if self.layers % 2:
            raise ValueError("layers must be even for a circuit and its mirror inverse")
        if self.t2_us > 2 * self.t1_us:
            raise ValueError("t2_us cannot exceed twice t1_us")
        if self.baseline_gate_ns * (1 + self.pulse_duration_increase) > 1_000_000:
            raise ValueError("optimized gate duration cannot exceed 1,000,000 ns")
        gate_count = self.n_qubits * self.layers // 2
        if self.shots * gate_count > MAX_TRAJECTORY_GATE_UPDATES:
            raise ValueError("Requested simulation is too large; reduce shots, layers, or qubits")
        return self


def coerce_scenario(value: Scenario | dict) -> Scenario:
    """Validate even an existing instance, including unsafe model_copy updates."""

    return Scenario.model_validate(value.model_dump() if isinstance(value, Scenario) else value)
