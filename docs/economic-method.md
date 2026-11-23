# From a quantum benchmark to a commercial decision

QubitYield evaluates the fictional Calibration Contract on page 5 of the course hackathon. The central distinction is between a promising technical experiment and a purchase that creates customer value. The model can prioritize pulse optimization for validation while recommending against signing the proposed $5M contract at its current price.

The case provides no realized revenue, willingness to pay, vendor delivery cost, application-quality threshold, or device-wide validation. Dollar results are conditional scenarios. They are not forecasts, valuations of a real company, or demonstrated quantum advantage.

## 1. What the experiment measures

The quantum engine measures the probability of a successful all-zero outcome in a controlled Clifford mirror circuit. It is a reproducible benchmark in a stated noise model. It is not the success probability of an arbitrary chemistry, finance, optimization, or error-correction application.

Each benchmark uses `n_qubits / 2` disjoint entangling gates per layer. At the case values this gives 200 two-qubit gates, but the entangling part lasts 20 x 300 ns = 6 us because gates within a layer run in parallel. The pulse proposal makes that 8.4 us. The economic model adds an explicitly assumed 100 us of reset, readout and host overhead per shot to both. Single-qubit gates are ideal and have zero duration in this controlled experiment. A real replay must include their cost.

For measured benchmark success probability `p` and shot-cycle time `t`, successful-shot throughput is `p / t`. The pulse capacity multiplier is

```
R = (p_pulse / t_pulse) / (p_baseline / t_baseline)
t_baseline = overhead_us + layers * baseline_gate_ns / 1000
t_pulse = overhead_us + layers * baseline_gate_ns * (1 + duration_increase) / 1000
```

QubitYield recalculates cycle times when overhead changes. It does not blindly accept a cached or user-supplied throughput ratio. The ratio can be below one: reduced error is not automatically worth a longer gate.

In `reported_total` mode the case's gate errors are interpreted as total average gate infidelities. T1/T2 loss during those gates is not applied a second time. `control_only` is an explicitly alternate interpretation with additional Pauli-twirled relaxation. See [quantum-method.md](quantum-method.md) for the noise model and its limits.

## 2. Availability is not demand

The baseline has 24 - 8 = 16 nominal available hours/day. The case's 70% booked fraction implies 11.2 booked hours/day. `demand_hours_per_day` is the active demand input; `booking_utilization` remains the observed anchor. Change demand to test a future backlog rather than silently assuming one.

The default reading of "70% faster" is 1.7 times the calibration rate, so calibration time is divided by 1.7. This is a 41.18% time reduction, not 70%. The UI also tests the alternate 70%-less-time interpretation.

The case says 35% of tasks are already automated. It does not say those tasks consume 35% of the eight hours. The model explicitly assumes task count is proportional to duration, so only 65% of time remains addressable. This assumption should be replaced by a task-duration audit. It can also understate value if the new tool can accelerate already-automated tasks; no such incremental capability is established in the case.

The default 70% transfer factor between the 10-qubit pilot and the 100-qubit device is an analyst assumption, not a probability or a measured scaling law. Likewise, 25% overlap between recovered time and useful customer windows is an assumption chosen to interrogate the statement that "most" calibration is overnight.

```
physical_saved_hours = calibration_hours
                     * (1 - already_automated)
                     * time_reduction
                     * scale_realization

reachable_saved_hours = physical_saved_hours * monetizable_overlap
baseline_booked = min(demand, 24 - calibration_hours)
AI_booked = min(demand, 24 - calibration_hours + reachable_saved_hours)
```

At the defaults, 1.499 physical hours are recovered, 0.375 are assumed reachable, and zero additional hours are booked because 11.2 hours of demand already fit within 16 available hours. The daily schedule still sums to 24 hours: unbooked recovered time is idle time, not imaginary revenue.

This is a deliberately simple fungible-demand model. A 70%-booked device can still suffer peak-time queues, cancellation costs or staffing constraints. Time-stamped bookings and calibration logs are the next evidence required. The overlap and demand controls stress-test the assumption; they do not replace a scheduling study.

## 3. The explicit value bridge

Annual baseline-equivalent productive hours are defined as booked wall-clock hours multiplied by operating days and by throughput relative to the baseline. For calibration the relative throughput is one; for the pulse option it is `R`.

These are normalized capacity units. They may exceed the actual hours in a year because the proposed device produces more benchmark successes per hour. They are not wall-clock hours or a claim that an application completes with fewer paid jobs.

Two valuation modes make the commercial claim explicit. Let `B` denote baseline booked hours/year and `R` the pulse successful-shot rate ratio.

```
additional_output:
    pulse_value_hours = B * (R - 1)
    calibration_value_hours = extra_booked_hours

fixed_output_savings:
    pulse_value_hours = B * (1 - 1/R)
    calibration_value_hours = 0

annual_benefit = value_hours * value_per_productive_hour * value_realization
```

The first mode values more useful output in the same booked runtime and requires demand for that output. The second holds expected useful benchmark output constant and values the runtime saved: work that previously took `B` hours takes `B/R` hours. It only creates money if costs are avoidable or the released time is redeployed. It does not imply that a fixed annual equipment bill shrinks. A threefold throughput gain would create `2B` of additional baseline-equivalent output capacity but save only `2B/3` of the original booked time. Treating these as interchangeable would materially overvalue a cost-saving proposal.

Calibration adds availability but does not accelerate already-booked work, so it receives zero same-output runtime-saving value. Extra bookings belong to the additional-output case. The exported `value_hours_year` is the quantity used in the financial calculation; `incremental_useful_hours_year` remains the physical extra-output capacity metric in both modes. A zero pulse success rate cannot fulfill fixed output and is rejected. A slowdown that requires more daily time than is available produces an explicit infeasibility warning.

The default $1,000 per valued hour and 35% realization fraction are unvalidated, visible inputs. Interpret the dollar rate as marginal contribution or avoided cost. Do not substitute gross revenue without deducting incremental costs. Interpret realization as the fraction of the chosen output or time-saving quantity that really translates into monetizable application benefit. It is not a statistical confidence level.

Quality improvements can increase useful output within existing bookings. Selling that output, charging a premium, reducing retries, or retaining customers requires a customer-specific commercial explanation. The model intentionally makes that disputed link visible rather than setting it implicitly to 100%.

Negative incremental throughput produces a negative annual benefit. Zero demand or zero commercial realization produces zero capacity value even if the underlying hardware gets better.

## 4. Lower-cost controls and sunk costs

The advertised standalone system costs $2M x 70% = $1.4M. Customer integration costs 3 engineers x 6/12 year x $300K/year = $450K.

If a new $2M purchase was already necessary, the standalone offer saves at most $150K before unprovided costs or benefits. If the current $2M system is already installed and replacement is unnecessary, its purchase price is sunk. Replacing it costs $1.85M and has no established compensating benefit. `replacement_due` switches these cases.

The proposed $5M total contract is a different price from the advertised $1.4M hardware quote. For comparisons at the proposed contract price, QubitYield assumes the $5M includes the selected product and includes the hardware when controls are selected. It therefore does not charge $1.4M again. Before contract payments, the controls option's incremental value is:

```
gross_value = (2M if replacement already required, otherwise 0) - 450K integration
```

Changing the advertised hardware discount affects the standalone procurement comparison, but it does not change an independently fixed $5M all-inclusive contract. If a real quote excludes hardware, its scope must be modeled differently before use.

Equal performance, reliability and support for cheaper controls is an assumption. The code recognizes no capacity benefit for controls. It treats integration and any avoided procurement as time-zero costs/benefits, does not invent resale value for the installed system, and includes no terminal value.

## 5. Cash flows and price ceilings

The default horizon is three years with a 12% discount rate. The default deployment delay is six months, so year-one capacity benefits are half of their steady-state annual value. Later years receive the full annual benefit. Delays beyond the horizon create no recurring benefit.

The contract is paid in equal end-of-year installments. A deployment delay does not defer payment unless the contract actually says so. All timing assumptions are visible in `financial_basis` and in the exported annual cash flows.

```
customer_NPV = upfront_benefit
             + sum((annual_benefit * active_fraction(year) - annual_fee)
                   / (1 + discount_rate)**year)
```

`gross_value_pv_usd` is customer benefit present value before the contract fee. For positive gross value, `price_ceiling_usd` is a nominal total price under the same equal-installment schedule that makes customer NPV zero. It is not the present value and is not a recommended price. A zero ceiling may instead mean no nonnegative price can break even: `price_ceiling_feasible` is false when gross value is negative, such as unnecessary controls with unavoidable integration costs. A sensible negotiated price needs customer surplus, delivery-cost coverage, risk sharing and measured acceptance gates. Vendor costs are absent from the case, so the project does not assert vendor profit or a viable gross margin.

`break_even_value_per_hour_usd` reports the assumed dollar value required for the target quote to break even. It is null if the option has no positive incremental monetizable capacity. No infinity is disguised as a usable price.

## 6. Decision and uncertainty

The recommendation separates two questions:

1. Which alternative has the greatest modeled gross customer value and deserves validation?
2. Is any alternative better than doing nothing at the proposed contract price?

The first determines the validation priority. The second appears as `best_at_current_quote`. A positive modeled NPV remains a conditional go after validation. A promising improvement with a negative quoted NPV calls for renegotiation. If no option has positive gross value, the recommendation is to keep the current system.

The tornado analysis changes one economic assumption at a time while reusing the same physical evidence. The heatmap jointly varies the dollar value and realization fraction and includes the no-purchase baseline. These are deterministic sensitivity calculations, not posterior probabilities or simulated confidence about a business outcome. Physical-input changes require a new matched quantum experiment.

The critical next experiment is a customer workload replay at matched wall-clock budgets, together with actual booking and calibration logs. Acceptance should concern useful application output and agreed economic value, not just a headline gate error or percentage of calibration tasks automated.

## Reproducibility and checks

The economics has no hidden random draws. `Scenario` rejects nonfinite values, out-of-range percentages, impossible T2/T1 combinations, and odd mirror-circuit dimensions. Tests cover time conservation, no-demand and no-realization cases, sunk versus avoidable controls costs, payment timing, delayed benefits, break-even prices, longer-gate penalties, and reconstruction of NPV from exported cash flows. No customer money is implied by a scientific benchmark alone.
