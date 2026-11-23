# Command-line workbench

Run from the project root after installing the Python package. `qubityield --help`
lists the same commands on Linux, macOS and Windows. Make is optional.

## Evaluate one scenario

```sh
qubityield evaluate --scenario data/default_scenario.json --output artifacts/my_analysis.json
```

Omitted fields use explicit validated defaults. `--shots` overrides the scenario's
shot count. JSON files are limited to 1 MiB, reject duplicate keys/nonfinite numbers
and cap nesting at 32 levels. Output includes full inputs, counts and provenance.

## Compare named scenarios

```sh
qubityield compare --scenarios data/comparison_scenarios.json --output artifacts/comparison.json --csv artifacts/comparison.csv
```

The input is a list of 1 to 16 objects shaped as `{"name":"Scenario name","scenario":{}}`.
Names must be unique after trimming. All items validate before any computation
starts. The JSON retains every full result; the CSV contains a compact comparison.
Formula-like text is escaped in CSV, while negative financial numbers remain numbers.
The best purchase after fees can differ from the next technical validation priority.

## Commercial strategy

```sh
qubityield stress --output artifacts/stress.json
qubityield pricing --output artifacts/pricing.json
```

Add `--request path.json` to supply assumptions. Both commands use the same models
as `/api/stress` and `/api/pricing`. Each computes one matching physical benchmark
and then evaluates the commercial model. Neither runs a new quantum experiment
for every grid cell. See [decision-tools.md](decision-tools.md) for complete schemas.

## Evidence integrity

```sh
python scripts/build_manifest.py
qubityield verify-manifest --root . --manifest artifacts/manifest.json
```

Generate a manifest only after finishing the evidence and both frontend builds.
Keep the original when checking received files. Regenerating it first would accept
the current contents as the new reference and defeat a tamper check.

The verifier checks declared relative paths, file sizes and SHA-256 hashes. It
rejects path traversal and symlinks that resolve outside the project root. It does
not authenticate the author and does not report files absent from the manifest.
An unchanged manifest passes with exit code 0; changed or missing files return 1;
invalid input returns 2.

## Reproduction and serving

```sh
qubityield reproduce
python scripts/validate_qiskit.py
python scripts/execute_notebook.py
npm run build --prefix web
npm run build:preview --prefix web
python scripts/build_manifest.py
qubityield verify-manifest
qubityield serve
```

The research extra is needed for independent Aer checks and notebook execution.
`reproduce --quick` skips multi-seed robustness. It is an iteration option, not
the final verification workflow. The server binds to localhost by default.
