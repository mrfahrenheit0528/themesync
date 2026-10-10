"""
Re-executes notebooks/results_analysis.ipynb in place and saves its outputs;
the figures land in results/figures/ (PNG at 300 dpi and PDF).

Needs nbformat, nbclient and ipykernel in the environment
(pip install nbformat nbclient ipykernel). The notebook's kernelspec is kept
as it is, so the file still opens with the server's kernel.

Usage (from the repo root):
  python notebooks/run_notebook.py
"""
import os
import sys

import nbformat
from nbclient import NotebookClient

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "results_analysis.ipynb")

nb = nbformat.read(PATH, as_version=4)
spec = dict(nb.metadata.get("kernelspec", {}))
NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": HERE}},
               allow_errors=True).execute()
errors = [(i, o.get("ename"), o.get("evalue")) for i, c in enumerate(nb.cells) if c.cell_type == "code"
          for o in c.get("outputs", []) if o.get("output_type") == "error"]
nb.metadata["kernelspec"] = spec
nbformat.write(nb, PATH)
print("errors:", errors or "none")
sys.exit(1 if errors else 0)
