"""Generate every submitted number, chart, and memo from the executable model."""

from __future__ import annotations

import csv
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from qubityield.analysis import evaluate, save_analysis
from qubityield.economics import evaluate_economics
from qubityield.models import Scenario
from qubityield.paths import project_root
from qubityield.quantum import compare_benchmarks

COLORS = {"baseline": "#87968e", "calibration": "#db965b", "pulse": "#147d69", "control": "#8175a9"}


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value) / 1_000_000:,.2f}M" if abs(value) >= 1_000_000 else f"{sign}${abs(value):,.0f}"


def plot_decision(result: dict, output: Path) -> None:
    """Publication-style evidence figure, with honest units and uncertainty scope."""
    s = Scenario.model_validate(result["scenario"])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    fig.set_facecolor("#f8f7f2")
    for ax in axes.flat:
        ax.set_facecolor("#f8f7f2")
    depth = result["depth_curve"]
    ax = axes[0, 0]
    for key, label in (("baseline", "Current gates"), ("pulse", "Optimized pulses")):
        xs = [r["layers"] for r in depth]
        ys = [r[key] * 100 for r in depth]
        ax.plot(xs, ys, color=COLORS[key], marker="o", markersize=4, label=label)
        ax.fill_between(xs, [r[key + "_low"] * 100 for r in depth], [r[key + "_high"] * 100 for r in depth], color=COLORS[key], alpha=0.14)
    ax.set(title="A. Same circuit family, different gate quality", xlabel="Entangling layers (includes inverse)", ylabel="All-zero return probability (%)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.15)

    ax = axes[0, 1]
    options = [o for o in result["options"] if o["id"] != "baseline"]
    names = ["AI calibration", "Pulse optimization", "Lower-cost controls"]
    vals = [o["customer_npv_usd"] / 1e6 for o in options]
    bars = ax.barh(names, vals, color=[COLORS[o["id"]] for o in options], height=0.5)
    ax.axvline(0, color="#173d37", lw=0.8)
    for bar, val in zip(bars, vals, strict=True):
        ax.text(val + (0.12 if val >= 0 else -0.12), bar.get_y() + bar.get_height() / 2, f"{val:+.2f}", va="center", ha="left" if val >= 0 else "right", fontsize=10)
    ax.set(title=f"B. Value after the {_money(s.contract_total)} contract", xlabel="Incremental customer NPV ($M)")
    ax.invert_yaxis()
    ax.margins(x=0.25)

    ax = axes[1, 0]
    y = [0, 1]
    for index, name in enumerate(("baseline", "calibration")):
        schedule = result["schedule"][name]
        left = 0.0
        for key, color in (("calibration", "#db965b"), ("booked", "#147d69"), ("idle", "#d7dcd2")):
            width = schedule[key]
            ax.barh(index, width, left=left, color=color, height=0.5, label=key.capitalize() if index == 0 else None)
            if width > 1.2:
                ax.text(left + width / 2, index, f"{width:.1f}h", ha="center", va="center", color="#102f2a")
            left += width
    ax.set(yticks=y, yticklabels=["Current", "AI calibration"], xlim=(0, 24), xlabel="Hours per day", title="C. More availability can remain unsold")
    ax.invert_yaxis()
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.42), fontsize=9)

    ax = axes[1, 1]
    prices = np.linspace(0, min(1_000_000, max(2500, s.value_per_productive_hour * 1.25)), 101)
    target = result["recommendation"]["id"]
    if target == "baseline":
        target = "pulse"
    target_label = {"pulse": "Pulse", "calibration": "Calibration", "control": "Controls"}[target]
    for realization, style in ((0.10, ":"), (s.value_realization, "-"), (0.70, "--")):
        ys = []
        for price in prices:
            altered = s.model_copy(update={"value_per_productive_hour": float(price), "value_realization": realization})
            r = evaluate_economics(altered, result["benchmark"], include_sensitivity=False)
            ys.append(next(o["customer_npv_usd"] for o in r["options"] if o["id"] == target) / 1e6)
        ax.plot(prices, ys, linestyle=style, color=COLORS[target], label=f"{realization:.0%} value realization")
    ax.axhline(0, color="#173d37", lw=0.8)
    ax.set(title="D. Commercial assumptions can reverse the decision", xlabel="Assumed value / baseline-equivalent hour ($)", ylabel=f"{target_label} customer NPV ($M)")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.15)
    fig.suptitle(f"QubitYield | Evidence before a {_money(s.contract_total)} commitment", fontsize=19, fontweight="bold", x=0.02, ha="left")
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def memo_sections(result: dict) -> list[tuple[str, str]]:
    by_id = {o["id"]: o for o in result["options"]}
    calibration = by_id["calibration"]
    b = result["benchmark"]
    s = result["scenario"]
    finance = result["financial_basis"]
    recommendation = result["recommendation"]
    selected = by_id[recommendation["id"]]
    base, upgraded = b["baseline"], b["pulse"]
    cap = selected["price_ceiling_usd"]
    break_even = selected["break_even_value_per_hour_usd"]
    if selected["id"] == "baseline":
        decision = (
            f"Keep the current system. No upgrade creates positive modeled gross customer value in this scenario, "
            f"so do not commit to the proposed {_money(s['contract_total'])} contract. "
            "First establish a customer application benefit and a credible way to capture it."
        )
        pricing = "The modeled decision supports no positive contract fee for an upgrade under these assumptions."
    else:
        decision = (
            f"Prioritize a gated {selected['label'].lower()} pilot. The contract verdict is "
            f"{recommendation['contract_verdict'].lower()}. At the proposed {_money(s['contract_total'])} "
            f"total fee, this option has {_money(selected['customer_npv_usd'])} incremental customer NPV "
            f"over {s['contract_years']} years. This is a conditional scenario result, not validated willingness to pay."
        )
        pricing = (
            f"For {selected['label'].lower()}, the zero-customer-NPV ceiling is {_money(cap)} "
            f"in equal annual installments over {s['contract_years']} years, not a price recommendation. "
            f"An illustrative 30% share of verified value would imply about {_money(.3 * cap)} on that schedule."
        )
    threshold = (
        f"The break-even productive-hour value for the selected option is {_money(break_even)}/hour "
        "at the same realization fraction."
        if break_even is not None
        else "The selected option has no positive incremental capacity denominator, so a productive-hour break-even value is not defined."
    )
    interpretation = (
        f"a {s['ai_speed_claim']:.0%} higher rate"
        if s["ai_speed_interpretation"] == "rate_increase"
        else f"{s['ai_speed_claim']:.0%} less time"
    )
    hypothesis = "survived" if recommendation["survived"] else "did not survive"
    controls_if_due = s["control_cost"] - finance["control_hardware_quote_usd"] - finance["control_integration_cost_usd"]
    controls_outlay = finance["control_hardware_quote_usd"] + finance["control_integration_cost_usd"]
    noise_limit = (
        "The selected reported-total error budget already includes gate-time decoherence; adding a T1/T2 penalty again would double count."
        if s["noise_mode"] == "reported_total"
        else "The selected control-only interpretation adds a Pauli-twirled approximation to thermal relaxation; it does not preserve amplitude damping's nonunital shift."
    )
    valuation = (
        "This scenario values the booked time saved for a fixed amount of useful benchmark output, B*(1-1/R). Only genuinely avoidable costs or verified redeployment create financial savings; calibration has no same-output execution speedup."
        if s["value_mode"] == "fixed_output_savings"
        else "This scenario values additional useful output, B*(R-1), not fixed-output cost savings; it requires demand and a customer application-value mechanism."
    )
    if selected["id"] == "pulse":
        other_mode = "fixed_output_savings" if s["value_mode"] == "additional_output" else "additional_output"
        other = evaluate_economics(
            Scenario.model_validate({**s, "value_mode": other_mode}), b, include_sensitivity=False,
        )
        other_npv = next(o["customer_npv_usd"] for o in other["options"] if o["id"] == "pulse")
        other_label = "runtime saved for the same output" if other_mode == "fixed_output_savings" else "additional useful output"
        valuation += f" Valuing the same physical gain as {other_label} gives {_money(other_npv)} customer NPV with all other inputs unchanged."
    if selected["id"] == "control":
        first_validation = "First verify that an equivalent controls purchase is actually required, obtain an inclusive quote, and measure integration effort and performance parity on the current workload."
    elif selected["id"] == "calibration":
        first_validation = "First audit duration-weighted calibration tasks and time-stamped bookings. Establish that the recovered windows have unmet customer demand and that the pilot time savings survive larger subsystems."
    elif selected["id"] == "baseline":
        first_validation = "First establish unmet application needs and an agreed dollar value for meeting them. Do not buy an upgrade solely because its benchmark number improves."
    else:
        first_validation = f"First confirm whether the proposed {s['pulse_gate_error']:.2%} error is a total measured gate error at {s['baseline_gate_ns'] * (1 + s['pulse_duration_increase']):g} ns."
    return [
        ("Decision", decision),
        ("Initial hypothesis and what changed", f"The initial calibration-first hypothesis {hypothesis}. This scenario has {by_id['baseline']['available_hours_day']:g} nominal available hours/day, {s['demand_hours_per_day']:g} hours/day of demand and {by_id['baseline']['booked_hours_day']:g} booked hours/day. Reading the AI claim as {interpretation} gives a {finance['calibration_time_reduction']:.2%} time reduction. With {1-s['already_automated']:.0%} assumed time eligibility, {s['scale_realization']:.0%} scale transfer and {s['monetizable_overlap']:.0%} useful-window overlap, automation recovers {calibration['recovered_hours_day']:.3f} physical hours/day and {calibration['usable_recovered_hours_day']:.3f} demand-accessible hours/day. It adds {calibration['incremental_useful_hours_year']:.0f} booked hours/year at the entered demand. The task-duration and demand assumptions need customer logs."),
        ("Computational evidence", f"A seeded {s['n_qubits']}-qubit Clifford mirror contains {base['gate_count']} two-qubit gates across {s['layers']} parallel entangling layers. At seed {s['seed']}, current gates return the known correct bitstring in {base['successes']:,}/{base['shots']:,} shots ({base['p_success']:.2%}); proposed pulses do so in {upgraded['successes']:,}/{upgraded['shots']:,} ({upgraded['p_success']:.2%}). Including {s['fixed_overhead_us']:g} microseconds of assumed overhead, cycles take {b['baseline_cycle_us']:g} versus {b['pulse_cycle_us']:g} microseconds. The proposed successful-shot rate is {b['throughput_ratio']:.3f} times the baseline. Per-circuit intervals quantify shot sampling only. Multi-seed and independent Qiskit validation routines are provided; their saved reports identify their own tested configurations and do not automatically validate every edited scenario. No QPU was used."),
        ("Price and alternatives", f"Assuming ${s['value_per_productive_hour']:,.0f} of contribution or avoided cost per valued hour and {s['value_realization']:.0%} value realization gives {_money(selected['annual_benefit_usd'])}/year for the selected option after rollout. {valuation} The horizon uses {s['discount_rate']:.0%} discounting and a {s['rollout_months']:g}-month rollout. {threshold} {pricing} Separately, the advertised controls quote nets {_money(controls_if_due)} if an equivalent new purchase was already required, after {_money(finance['control_integration_cost_usd'])} of integration cost. Without a replacement need it creates {_money(controls_outlay)} of new outlay. The target {_money(s['contract_total'])} controls contract includes its hardware, preventing double counting."),
        ("What the customer should validate first", first_validation + " Run a matched wall-clock replay of the customer's actual workload, including readout, reset, single-qubit gates, leakage, drift and calibration outages. Pre-register the circuit or observable, error tolerance and useful-throughput acceptance rule; randomize comparison sessions across days and qubit regions. Record the full booking calendar. The original case's 10-qubit calibration pilot needs validation on larger subsystems before extrapolating to a 100-qubit processor."),
        ("Commercial terms and limitations", "If the validation gates justify a pilot, agree its scope and delivery-cost floor before spending; release deployment payments only after technical and application-value gates pass. Cap recurring fees at a negotiated share of verified incremental value, with rollback and reliability conditions. Vendor delivery cost is absent, so no vendor margin is claimed. The simulator uses independent stochastic faults, a homogeneous ring-connected synthetic workload and ideal local gates. " + noise_limit + " Mirror return is not general application correctness, and a 100-qubit device is not assumed to run five independent jobs. These are the main reasons to validate before committing."),
    ]


def write_memo(result: dict, output: Path, figure: Path) -> None:
    # Embed the fonts shipped with Matplotlib for portable, predictable PDF text.
    for name, weight in (("QSans", "normal"), ("QSans-Bold", "bold")):
        pdfmetrics.registerFont(TTFont(name, findfont(FontProperties(family="DejaVu Sans", weight=weight))))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="QTitle", fontName="QSans-Bold", fontSize=25, leading=29, textColor=colors.HexColor("#153e35"), spaceAfter=12))
    styles.add(ParagraphStyle(name="QMeta", fontName="QSans", fontSize=9, leading=13, textColor=colors.HexColor("#5c7066"), spaceAfter=16))
    styles.add(ParagraphStyle(name="QHead", fontName="QSans-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#147d69"), spaceBefore=9, spaceAfter=4))
    styles.add(ParagraphStyle(name="QBody", fontName="QSans", fontSize=9.5, leading=13.5, textColor=colors.HexColor("#23352d"), spaceAfter=7, alignment=TA_LEFT))
    doc = SimpleDocTemplate(str(output), pagesize=(612, 792), rightMargin=48, leftMargin=48, topMargin=42, bottomMargin=42, title="QubitYield: Executive Decision Memo", author="Jasper Sands")
    story = [Paragraph("The Calibration Contract", styles["QTitle"]), Paragraph("QubitYield | Challenge 04 | Executive decision memo<br/>Fictional case. Simulated evidence. AI-assisted implementation.", styles["QMeta"])]
    sections = memo_sections(result)
    for heading, body in sections[:3]:
        story.extend((Paragraph(escape(heading), styles["QHead"]), Paragraph(escape(body), styles["QBody"])))
    rows = [["Alternative", "Annual benefit*", f"{result['scenario']['contract_years']}-year customer NPV"]]
    for option in result["options"]:
        if option["id"] != "baseline":
            rows.append([option["label"], _money(option["annual_benefit_usd"]), _money(option["customer_npv_usd"])])
    table = Table(rows, colWidths=[184, 142, 190])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153e35")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "QSans-Bold"), ("FONTNAME", (0, 1), (-1, -1), "QSans"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 9), ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#d9dfd3"))]))
    story.extend((Spacer(1, 8), table, Paragraph("*Conditional modeled steady-state contribution or avoided cost, before contract fees. NPV includes rollout, fees and controls integration.", styles["QMeta"]), PageBreak()))
    story.append(Paragraph("Validation before scale", styles["QTitle"]))
    for heading, body in sections[3:]:
        story.extend((Paragraph(escape(heading), styles["QHead"]), Paragraph(escape(body), styles["QBody"])))
    story.extend((Paragraph("Evidence and sources", styles["QHead"]), Paragraph("Case: instructor-provided Lab-to-Market Hackathon, Session 11, November 19, 2026, p. 5. Reproduction: artifacts/analysis.json, options.csv, multi_seed.json, qiskit_validation.json and decision_landscape.png. Method references: Qiskit Aer depolarizing_error and device-noise documentation; Proctor et al., Phys. Rev. Lett. 129, 150502 (2022), doi:10.1103/PhysRevLett.129.150502. Full links and limitations are in docs/references.md.", styles["QBody"])))

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#d9dfd3"))
        canvas.line(48, 31, 564, 31)
        canvas.setFont("QSans", 8)
        canvas.setFillColor(colors.HexColor("#5c7066"))
        canvas.drawString(48, 19, result["evidence"]["experiment_id"] + " | Reproducible decision evidence")
        canvas.drawRightString(564, 19, str(doc.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    md = "# Executive decision memo\n\nFictional case. Simulated evidence. AI-assisted implementation.\n\n"
    for heading, body in sections:
        md += f"## {heading}\n\n{body}\n\n"
    md += "See [references](../docs/references.md), [raw evidence](analysis.json), and [result figure](decision_landscape.png).\n"
    output.with_suffix(".md").write_text(md, encoding="utf-8")


def write_notebook(result: dict, output: Path) -> None:
    try:
        import nbformat
    except ImportError:
        return
    nbf = nbformat.v4
    scenario_literal = repr(result["scenario"])
    nb = nbf.new_notebook(metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
    nb.cells = [
        nbf.new_markdown_cell("# QubitYield: The Calibration Contract\n\nA reproducible investigation of Challenge 4. All case data are fictional and all quantum results are simulated. See `docs/ai-assistance.md` for disclosure.\n\n## 1. Investigate\n\nWorking hypothesis: automate calibration first because eight hours/day looks like the largest loss. Falsifiers: recovered windows have no unmet demand, or pulse improvement produces greater validated application value. The experiment tests baseline, AI calibration, pulse optimization and cheaper controls."),
        nbf.new_code_cell(f"from pathlib import Path\nimport sys\nroot = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / 'data' / 'case_facts.json').exists())\nsys.path.insert(0, str(root / 'src'))\nfrom qubityield.models import Scenario\nfrom qubityield.analysis import evaluate\nfrom qubityield.quantum import compare_benchmarks\nscenario = Scenario.model_validate({scenario_literal})\nresult = evaluate(scenario)\nresult['evidence']"),
        nbf.new_markdown_cell("## 2. Experiment\n\nThe 20-qubit Clifford mirror uses 200 CX gates in 20 parallel layers. The known ideal output is all zero. The NumPy engine propagates actual Pauli faults; a separate Qiskit Aer adapter checks it independently. The default error is interpreted as total average gate infidelity. Coherence is not counted twice.\n\nPer-circuit intervals describe sampling error only. They do not quantify business uncertainty."),
        nbf.new_code_cell("import pandas as pd\npd.DataFrame([{\n    'proposal': name, 'successes': result['benchmark'][name]['successes'],\n    'shots': result['benchmark'][name]['shots'],\n    'return_probability': result['benchmark'][name]['p_success'],\n    'CI_low': result['benchmark'][name]['ci_low'], 'CI_high': result['benchmark'][name]['ci_high'],\n} for name in ['baseline', 'pulse']])"),
        nbf.new_code_cell("columns = ['label', 'booked_hours_day', 'incremental_useful_hours_year', 'annual_benefit_usd', 'customer_npv_usd']\npd.DataFrame(result['options'])[columns]"),
        nbf.new_code_cell("from IPython.display import Image, display\nfrom tempfile import TemporaryDirectory\nfrom qubityield.reporting import plot_decision\n# Render this notebook's own evidence, including when reports use a custom output folder.\nwith TemporaryDirectory(prefix='qubityield-notebook-') as directory:\n    figure_path = Path(directory) / 'decision_landscape.png'\n    plot_decision(result, figure_path)\n    display(Image(filename=str(figure_path)))"),
        nbf.new_markdown_cell("## Sensitivity and the strongest counter-case\n\nDollar value and commercial realization are unvalidated assumptions. Lower either enough and the proposed deal stops being worthwhile. Valuing more output also differs from saving runtime for the same output. New availability alone cannot generate demand."),
        nbf.new_code_cell("low_value = scenario.model_copy(update={'value_per_productive_hour': 250, 'value_realization': 0.10})\nlow_result = evaluate(low_value, include_depth=False)\n{'default_verdict': result['recommendation']['contract_verdict'], 'low_value_verdict': low_result['recommendation']['contract_verdict'], 'low_value_options': [{k: o[k] for k in ('label', 'customer_npv_usd')} for o in low_result['options']]}"),
        nbf.new_code_cell("same_work = scenario.model_copy(update={'value_mode': 'fixed_output_savings'})\nsavings_result = evaluate(same_work, include_depth=False)\npd.DataFrame([{'valuation': label, **next(o for o in item['options'] if o['id'] == 'pulse')} for label, item in [('Additional useful output', result), ('Same useful output, less runtime', savings_result)]])[['valuation', 'annual_benefit_usd', 'customer_npv_usd', 'price_ceiling_usd']]"),
        nbf.new_code_cell("# Five predeclared circuit seeds test circuit dependence. No best-seed selection.\nrobustness = compare_benchmarks(seeds=(7,17,29,43,71), shots=scenario.shots, noise_mode=scenario.noise_mode)\n{arm: {k: v for k, v in robustness[arm].items() if k != 'runs'} for arm in ('baseline','optimized')}"),
        nbf.new_markdown_cell("## Commercial stress and pricing\n\nA regular grid describes the stated assumption combinations. Its win coverage is not a probability of commercial success. Vendor costs are explicit illustrative assumptions. Pricing checks both nominal margin and discounted cash-flow break-even, using the same payment schedule as the customer's ceiling."),
        nbf.new_code_cell("from qubityield.decision_tools import StressRequest, PricingRequest, evaluate_stress, evaluate_pricing\nstress = evaluate_stress(StressRequest(scenario=scenario), result['benchmark'])\npd.DataFrame(stress['options'])[['label', 'worst_npv_usd', 'base_npv_usd', 'best_npv_usd', 'win_coverage', 'max_regret_usd']]"),
        nbf.new_code_cell("pricing = evaluate_pricing(PricingRequest(scenario=scenario), result['benchmark'])\npd.DataFrame(pricing['options'])[['label', 'customer_zero_npv_cap_usd', 'vendor_floor_usd', 'customer_share_target_usd', 'share_policy_feasible', 'status_label']]"),
        nbf.new_code_cell("# The selected share is a negotiation assumption, not a market fact.\nnegotiated = evaluate_pricing(PricingRequest(scenario=scenario, customer_value_share=0.35), result['benchmark'])\n{'nominal_margin_floor': pricing['nominal_margin_floor_usd'], 'discounted_cash_floor': pricing['discounted_break_even_floor_usd'], 'default_policy': pricing['recommendation'], 'alternative_share_policy': negotiated['recommendation']}"),
        nbf.new_markdown_cell("## 3. Recommend\n\nPrioritize pulse validation; the initial calibration-first hypothesis does not survive the stated demand. Validate matched-wall-clock customer application outcomes before committing the full contract. The price ceiling is a scenario-dependent zero-NPV bound, not a quote. See `artifacts/decision_memo.pdf` for the executive recommendation and `docs/pilot-plan.md` for the experiment gates.\n\n## Reproduce and audit\n\nRun `qubityield reproduce`, `pytest`, and `python scripts/validate_qiskit.py`. Case inputs, assumptions, source references, simulation counts, and code are all included. No claims of quantum advantage or real hardware measurements are made."),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, output)


def reproduce_all(output: Path, *, shots: int = 8192, quick: bool = False) -> dict[str, str]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scenario = Scenario(shots=shots)
    result = evaluate(scenario, refresh=True)
    save_analysis(result, output / "analysis.json")
    _write_csv(output / "options.csv", result["options"])
    _write_csv(output / "depth_sweep.csv", result["depth_curve"])
    _write_csv(output / "cashflows.csv", result["cashflows"])
    _write_csv(output / "sensitivity.csv", result["sensitivities"])
    _write_csv(output / "decision_map.csv", result["heatmap"])
    if not quick:
        multi = {mode: compare_benchmarks(shots=shots, noise_mode=mode) for mode in ("reported_total", "control_only")}
        save_analysis(multi, output / "multi_seed.json")
    variants = {
        "case_default": {},
        "low_commercial_value": {"value_per_productive_hour": 250, "value_realization": 0.10},
        "same_work_savings": {"value_mode": "fixed_output_savings"},
        "demand_backlog": {"demand_hours_per_day": 20, "monetizable_overlap": 0.75, "scale_realization": 1.0},
        "time_reduction_reading": {"ai_speed_interpretation": "time_reduction", "demand_hours_per_day": 20},
        "replacement_already_due": {"replacement_due": True},
        "no_fixed_overhead": {"fixed_overhead_us": 0},
        "control_only_noise": {"noise_mode": "control_only"},
    }
    scenario_results = {}
    rows = []
    for name, overrides in variants.items():
        altered = Scenario.model_validate({**scenario.model_dump(), **overrides})
        item = evaluate(altered, include_depth=False)
        scenario_results[name] = item
        for option in item["options"]:
            rows.append({"scenario_name": name, **option})
    save_analysis(scenario_results, output / "scenarios.json")
    _write_csv(output / "scenarios.csv", rows)
    from qubityield.decision_tools import (
        PricingRequest,
        StressRequest,
        evaluate_pricing,
        evaluate_stress,
    )
    from qubityield.portable import compare_scenarios, read_json, write_comparison_csv
    tools = {
        "stress": evaluate_stress(StressRequest(scenario=scenario), result["benchmark"]),
        "pricing": evaluate_pricing(PricingRequest(scenario=scenario), result["benchmark"]),
    }
    for name, tool_result in tools.items():
        tool_result["evidence"] = result["evidence"]
        tool_result["benchmark"] = result["benchmark"]
        save_analysis(tool_result, output / f"{name}.json")
    batch_path = project_root() / "data" / "comparison_scenarios.json"
    if batch_path.is_file():
        batch = read_json(batch_path)
        for item in batch:
            item["scenario"] = {**scenario.model_dump(), **item["scenario"]}
        comparison = compare_scenarios(batch)
        save_analysis(comparison, output / "comparison.json")
        write_comparison_csv(comparison, output / "comparison.csv")
    figure = output / "decision_landscape.png"
    plot_decision(result, figure)
    write_memo(result, output / "decision_memo.pdf", figure)
    notebook = project_root() / "notebooks" / "calibration_contract.ipynb"
    write_notebook(result, notebook)
    public = project_root() / "web" / "public"
    if public.is_dir():
        save_analysis(result, public / "demo.json")
        save_analysis(tools, public / "tools.json")
    return {
        "analysis": str(output / "analysis.json"),
        "figure": str(figure),
        "memo": str(output / "decision_memo.pdf"),
        "table": str(output / "options.csv"),
        "notebook": str(notebook),
        "stress": str(output / "stress.json"),
        "pricing": str(output / "pricing.json"),
    }
