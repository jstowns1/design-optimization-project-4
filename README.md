# Project 4 · Steel Footbridge Design Optimization

**MAE 494/598 · PDE-Constrained Design Optimization**

This project finds a lighter design for a 15 m steel Pratt footbridge carrying pedestrian load and self-weight. The design variables are the outer radii of 109 circular tubes and two parameters that control the shape of the top chord. The optimization enforces limits on static stress, fatigue, deck deflection, vibration, buckling, and member slenderness.

[Open the live report and interactive 3D comparison](https://jstowns1.github.io/design-optimization-project-4/)

## Results at a glance

| Result | Value |
| --- | ---: |
| Initial mass | 9,528.29 kg |
| Optimized mass | 6,022.48 kg |
| Mass reduction | **36.8%** |
| Optimized peak deck deflection | 9.19 mm (37.5 mm limit) |
| Optimized buckling load factor | 9.85 (minimum 3.0) |
| Verification ladder | V1–V6 passed |

The optimized design met all six limits on both the production and refined meshes. Fatigue and frequency governed the solution. The report compares the initial design, the optimized design, the result without the buckling constraint, and the refined-mesh recheck. [Full results and interpretation](https://jstowns1.github.io/design-optimization-project-4/#nonlinear-component-and-results)

## Run on Windows

Open this repository in VS Code and open a **PowerShell** terminal in the folder that contains this README and `run_project.py`. Use Python 3.10 or newer.

### 1. Set up the environment once

Create a project-local virtual environment.

```powershell
py -3 -m venv .venv
```

<details>
<summary>If Windows cannot find the <code>py</code> launcher</summary>

On the Codex workstation used for this project, this command creates the same environment with the bundled Python.

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
```

</details>

Install the numerical dependencies into that environment.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

### 2. Verify and regenerate the results

```powershell
.\.venv\Scripts\python.exe .\run_project.py
```

The script runs V1–V6 before optimization. It then runs SLSQP from two starting designs, repeats the study without the buckling constraint, and rechecks the selected design on a finer mesh. A successful run ends by writing [assets/results.json](assets/results.json), which supplies the report's tables, plots, engineering drawings, and 3D viewer.

### Run only the V1 cantilever check

```powershell
.\.venv\Scripts\python.exe .\verify_v1.py
```

V1 uses Python's standard library and should report **7.18857015 mm downward**. The comparison and original hand calculation are in [benchmarks.md](benchmarks.md).

## Repository guide

| File | Purpose |
| --- | --- |
| [run_project.py](run_project.py) | Runs verification and optimization and writes the report data |
| [frame3d.py](frame3d.py) | Defines the 3D beam elements, sparse assembly, and modal and buckling solves |
| [bridge.py](bridge.py) | Defines the bridge geometry, loads, constraints, and adjoint derivatives |
| [verify_project.py](verify_project.py) | Checks reference solutions, mesh convergence, equilibrium, and sensitivities |
| [index.md](index.md) | Contains the technical report served by GitHub Pages |
| [assets/](assets/) | Contains generated results, interactive figures, the 3D viewer, and report styles |

## How the report is published

GitHub Pages builds the report from the root of `main`. Jekyll renders `index.md`, and the browser loads the generated results. The 3D comparison uses WebGL and a pinned version of Three.js. [View the published report](https://jstowns1.github.io/design-optimization-project-4/)
