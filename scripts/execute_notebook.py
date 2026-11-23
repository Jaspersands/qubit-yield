"""Execute this project's ordinary-Python notebook without opening kernel sockets.

Cells share a Python namespace. IPython captures rich display output; the final
expression in each cell becomes its execute_result. This runner deliberately
does not support notebook magics or shell escapes. Standard Jupyter also works.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import nbformat
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / "notebooks" / "calibration_contract.ipynb"
    notebook = nbformat.read(path, as_version=4)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.chdir(ROOT)
    shell = InteractiveShell.instance()
    namespace = {"__name__": "__main__"}
    count = 0
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        count += 1
        filename = f"{path.name}:cell-{count}"
        tree = ast.parse(cell.source, filename=filename)
        final = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
        value = None
        with capture_output(stdout=True, stderr=True, display=True) as captured:
            exec(compile(tree, filename, "exec"), namespace)
            if final is not None:
                value = eval(compile(ast.Expression(final.value), filename, "eval"), namespace)
        outputs = []
        if captured.stdout:
            outputs.append(nbformat.v4.new_output("stream", name="stdout", text=captured.stdout))
        if captured.stderr:
            outputs.append(nbformat.v4.new_output("stream", name="stderr", text=captured.stderr))
        for rich in captured.outputs:
            outputs.append(nbformat.v4.new_output("display_data", data=rich.data, metadata=rich.metadata))
        if value is not None:
            data, metadata = shell.display_formatter.format(value)
            outputs.append(nbformat.v4.new_output(
                "execute_result", data=data, metadata=metadata, execution_count=count,
            ))
        cell.execution_count = count
        cell.outputs = outputs
    notebook.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook.metadata["qubityield_execution"] = {
        "method": "in-process Python with IPython rich-output capture",
        "code_cells_executed": count,
        "note": "No kernel sockets required. All saved outputs came from executing the cells.",
    }
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    print(f"Executed {count} notebook cells without errors: {path}")


if __name__ == "__main__":
    main()
