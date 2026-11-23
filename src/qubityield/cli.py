"""Command-line entry points for reproduction, scenario evaluation, and the workbench."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qubityield import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qubityield", description="Reproducible quantum hardware decisions")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("evaluate", help="Evaluate a scenario and save JSON evidence")
    run.add_argument("--scenario", type=Path, help="JSON scenario; omitted fields use explicit defaults")
    run.add_argument("--output", type=Path, default=Path("artifacts/analysis.json"))
    run.add_argument("--shots", type=int, help="Override shots per arm")
    compare = commands.add_parser("compare", help="Compare 1 to 16 named scenarios with full evidence")
    compare.add_argument("--scenarios", type=Path, required=True, help="JSON list of {name, scenario} objects")
    compare.add_argument("--output", type=Path, default=Path("artifacts/comparison.json"))
    compare.add_argument("--csv", type=Path, help="Optional spreadsheet-safe comparison table")
    for name, help_text in (("stress", "Evaluate a bounded commercial sensitivity grid"),
                            ("pricing", "Compare vendor price floors with customer value ceilings")):
        tool = commands.add_parser(name, help=help_text)
        tool.add_argument("--request", type=Path, help="JSON request matching the API; omitted fields use defaults")
        tool.add_argument("--output", type=Path, default=Path(f"artifacts/{name}.json"))
    integrity = commands.add_parser("verify-manifest", help="Detect changed or missing files in an integrity manifest")
    integrity.add_argument("--manifest", type=Path, default=Path("artifacts/manifest.json"))
    integrity.add_argument("--root", type=Path, default=Path("."), help="Project root for relative manifest paths")
    reproduce = commands.add_parser("reproduce", help="Regenerate benchmark, figures, tables, memo, and notebook")
    reproduce.add_argument("--output", type=Path, default=Path("artifacts"))
    reproduce.add_argument("--shots", type=int, default=8192)
    reproduce.add_argument("--quick", action="store_true", help="Skip multi-seed robustness; notebook execution is a separate script")
    serve = commands.add_parser("serve", help="Serve API and built dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn
        uvicorn.run("qubityield.api:app", host=args.host, port=args.port, reload=args.reload)
        return 0
    from qubityield.analysis import evaluate, save_analysis
    from qubityield.models import Scenario
    from qubityield.portable import (
        compare_scenarios,
        read_json,
        require_distinct_outputs,
        verify_manifest,
        write_comparison_csv,
    )
    try:
        if args.command == "evaluate":
            values = read_json(args.scenario) if args.scenario else {}
            if not isinstance(values, dict):
                raise ValueError("A scenario must be a JSON object")
            if args.shots is not None:
                values["shots"] = args.shots
            result = evaluate(Scenario.model_validate(values), refresh=True)
            save_analysis(result, args.output)
            print(f"Evidence: {args.output.resolve()}")
            print(result["recommendation"]["title"])
            print(result["recommendation"]["summary"])
        elif args.command == "compare":
            if args.csv:
                require_distinct_outputs(args.output, args.csv)
            result = compare_scenarios(read_json(args.scenarios))
            save_analysis(result, args.output)
            if args.csv:
                write_comparison_csv(result, args.csv)
            print(f"Compared {result['count']} scenarios: {args.output.resolve()}")
        elif args.command in ("stress", "pricing"):
            from qubityield.decision_tools import (
                PricingRequest,
                StressRequest,
                evaluate_pricing,
                evaluate_stress,
            )
            model, calculate = (StressRequest, evaluate_stress) if args.command == "stress" else (PricingRequest, evaluate_pricing)
            request = model.model_validate(read_json(args.request) if args.request else {})
            analysis = evaluate(request.scenario, include_depth=False)
            result = calculate(request, analysis["benchmark"])
            result["evidence"] = analysis["evidence"]
            result["benchmark"] = analysis["benchmark"]
            save_analysis(result, args.output)
            print(f"Evidence: {args.output.resolve()}")
            print(result["recommendation"]["summary"])
        elif args.command == "verify-manifest":
            result = verify_manifest(read_json(args.manifest, max_bytes=5_242_880), args.root)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["valid"] else 1
        elif args.command == "reproduce":
            from qubityield.reporting import reproduce_all
            outputs = reproduce_all(args.output, shots=args.shots, quick=args.quick)
            for name, path in outputs.items():
                print(f"{name}: {path}")
    except (OSError, ValueError) as exc:
        print(f"qubityield: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
