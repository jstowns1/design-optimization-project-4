"""Verify, optimize, and regenerate the report data with one command."""

import json
import os
from pathlib import Path
from time import perf_counter

# These small sparse systems run faster with single-threaded BLAS.
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

import numpy as np
from scipy.optimize import minimize, nnls

from bridge import (Bridge, DECK_MASS, DECK_PRESSURE, DEFLECTION_LIMIT, FATIGUE_LIMIT,
                    MASS_SCALE, PLATE, RESPONSES, SPAN, WIDTH)
from frame3d import REFERENCE_RADIUS
from verify_project import verify_gradients, verify_structure


def kkt(bridge, x, evaluation, rows):
    """Estimate nonnegative multipliers with active constraint and bound gradients."""
    names = []
    columns = []
    residuals = []

    def add(name, residual, derivative):
        if residual >= -2e-5:
            names.append(name)
            columns.append(derivative)
            residuals.append(residual)

    for index in rows:
        name = RESPONSES[index] if index < 5 else f'Member {index - 4} slenderness'
        add(name, evaluation.constraints[index], evaluation.jacobian[index])
    for index, (lower, upper) in enumerate(bridge.bounds):
        unit = np.zeros_like(x)
        unit[index] = 1
        name = f'Member {index + 1} radius' if index < bridge.count else ('Portal height', 'Camber')[index - bridge.count]
        add(f'{name} lower bound', lower - x[index], -unit)
        add(f'{name} upper bound', x[index] - upper, unit)

    matrix = np.column_stack(columns)
    multipliers, _ = nnls(matrix, -evaluation.objective_gradient)
    stationarity = evaluation.objective_gradient + matrix @ multipliers
    return {'stationarity_inf': float(np.max(np.abs(stationarity))),
            'complementarity_inf': float(np.max(np.abs(multipliers * residuals))),
            'primal_violation': float(max(0, np.max(evaluation.constraints[rows]))),
            'multipliers': [dict(name=name, scaled=float(multiplier), kg=float(multiplier * MASS_SCALE),
                                 residual=float(residual))
                            for name, multiplier, residual in zip(names, multipliers, residuals)]}


def optimize(bridge, start, buckling):
    rows = np.r_[np.arange(5 if buckling else 4), np.arange(5, 5 + bridge.count)]
    cached_x = None
    cached = None
    history = []

    def evaluate(x):
        nonlocal cached_x, cached
        if not np.array_equal(cached_x, x):
            cached_x = x.copy()
            cached = bridge.evaluate(x)
        return cached

    def log(x):
        result = evaluate(x)
        history.append(dict(iteration=len(history), mass_kg=result.metrics['mass_kg'],
                            violation=float(max(0, result.constraints[rows].max()))))

    log(start)
    began = perf_counter()
    result = minimize(lambda x: evaluate(x).objective, start, method='SLSQP',
                      jac=lambda x: evaluate(x).objective_gradient, bounds=bridge.bounds,
                      constraints={'type': 'ineq', 'fun': lambda x: -evaluate(x).constraints[rows],
                                   'jac': lambda x: -evaluate(x).jacobian[rows]},
                      callback=log, options={'maxiter': 350, 'ftol': 2e-10})
    elapsed = perf_counter() - began
    evaluation = evaluate(result.x)
    certificate = kkt(bridge, result.x, evaluation, rows)
    if not result.success or certificate['primal_violation'] > 2e-6:
        raise RuntimeError(f'SLSQP ({buckling=}) failed: {result.message}, '
                           f'violation={certificate["primal_violation"]:.3g}')
    print(f'SLSQP ({buckling=}): {result.nit} iterations, {evaluation.metrics["mass_kg"]:.2f} kg, '
          f'KKT residual {certificate["stationarity_inf"]:.2g}', flush=True)
    run = {'iterations': int(result.nit), 'seconds': elapsed, 'message': str(result.message),
           'history': history, 'kkt': certificate}
    return result.x, evaluation, run


def snapshot(bridge, x, evaluation):
    state = evaluation.state
    mode = evaluation.mode.reshape(-1, 6)
    amplitude = np.max(np.linalg.norm(mode[:, :3], axis=1))
    return {'metrics': evaluation.metrics, 'portal_height_m': float(x[-2]), 'camber_m': float(x[-1]),
            'radii_m': (x[:bridge.count] * REFERENCE_RADIUS).tolist(),
            'nodes': evaluation.geometry.tolist(), 'static': state.displacement.reshape(-1, 6).tolist(),
            'mode': (mode / amplitude).tolist(), 'stress_mpa': (evaluation.stress / 1e6).tolist(),
            'g': evaluation.constraints[:5].tolist()}


def main():
    bridge = Bridge()
    checks = verify_structure(bridge)
    print('V1–V5 passed.', flush=True)
    gradient = verify_gradients(bridge)
    print(f'V6 passed. Max absolute Jacobian difference {gradient["max_absolute_jacobian_error"]:.2g}.',
          flush=True)

    initial = bridge.evaluate(bridge.initial, gradient=False)
    first = optimize(bridge, bridge.initial, buckling=True)
    alternate_start = np.r_[np.full(bridge.count, 0.095 / REFERENCE_RADIUS), 3.15, 0.10]
    second = optimize(bridge, alternate_start, buckling=True)
    x, final, run = min((first, second), key=lambda item: item[1].objective)
    x_no, final_no, run_no = optimize(bridge, bridge.initial, buckling=False)
    refined = Bridge(subdivisions=4).evaluate(x, gradient=False)
    result = {
        'mesh': {'members': bridge.count, 'elements': len(bridge.frame.edges),
                 'nodes': len(bridge.frame.nodes), 'variables': len(x),
                 'edges': bridge.frame.edges.tolist(), 'owner': bridge.owner.tolist(), 'labels': bridge.labels},
        'initial': snapshot(bridge, bridge.initial, initial), 'optimized': snapshot(bridge, x, final),
        'without_buckling': {'metrics': final_no.metrics, 'portal_height_m': float(x_no[-2]),
                             'camber_m': float(x_no[-1]), 'radii_m': (x_no[:bridge.count] * REFERENCE_RADIUS).tolist(),
                             'g': final_no.constraints[:5].tolist()},
        'refined': refined.metrics, 'verification': checks, 'gradients': gradient,
        'runs': {'selected': run, 'baseline': first[2], 'alternate': second[2], 'without_buckling': run_no},
        'start_masses_kg': [first[2]['history'][0]['mass_kg'], second[2]['history'][0]['mass_kg']],
        'final_masses_kg': [first[1].metrics['mass_kg'], second[1].metrics['mass_kg']],
        'plate': {'spacing_m': WIDTH / 4, 'pressure_pa': DECK_PRESSURE, 'mass_kg': DECK_MASS,
                  'stress_mpa': 0.75 * DECK_PRESSURE * (WIDTH / 4 / PLATE)**2 / 1e6,
                  'limit_mpa': FATIGUE_LIMIT / 1e6},
        'limits': {'stress_mpa': 160, 'goodman': 2, 'deflection_mm': DEFLECTION_LIMIT * 1000,
                   'frequency_hz': 3, 'buckling_factor': 3, 'slenderness': 200},
        'dimensions': {'span_m': SPAN, 'width_m': WIDTH, 'deck_thickness_m': PLATE},
    }
    output = Path(__file__).resolve().parent / 'assets' / 'results.json'
    output.parent.mkdir(exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n',
                         encoding='utf-8')
    temporary.replace(output)
    print(f'Wrote {output.relative_to(output.parents[1])}', flush=True)


if __name__ == '__main__':
    main()
