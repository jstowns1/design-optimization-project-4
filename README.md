# Project 4 · Steel footbridge design optimization

The solver sizes circular hollow sections and adjusts the top-chord profile of a 15 m Pratt through-truss. It runs the V1–V6 verification ladder before optimizing a design with and without the N1 buckling constraint. The original V1 hand calculation is in [benchmarks.md](benchmarks.md).

## Run on Windows

In the VS Code PowerShell terminal, open the repository folder. Use Python 3.10 or newer. Create the environment and install the two dependencies once.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the Windows Python launcher is unavailable on the Codex workstation, use its existing Python executable to create the environment.

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
```

Regenerate the solver results, every numerical report table, and the viewer data with one command.

```powershell
.\.venv\Scripts\python.exe .\run_project.py
```

The standalone V1 check uses the Python standard library.

```powershell
.\.venv\Scripts\python.exe .\verify_v1.py
```

## Serve the report

The GitHub Pages source is the repository root on the main branch. Jekyll processes [index.md](index.md), and the browser reads [assets/results.json](assets/results.json) for the tables, plots, and 3D comparison. The viewer uses WebGL and loads the pinned Three.js module over HTTPS.
