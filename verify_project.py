"""Independent reference cases and adjoint verification for the bridge model."""

from time import perf_counter

import numpy as np
from scipy.sparse.linalg import eigsh

from bridge import (DECK_MASS, DECK_PRESSURE, RESPONSES, SPAN, WIDTH,
                    deck_control_map, peak_deck_deflection)
from frame3d import AREA, DENSITY, E, G, GRAVITY, INERTIA, Frame
from verify_v1 import solve_cantilever


def reference_row(test, quantity, units, computed, reference, tolerance=1e-7):
    error = abs(computed - reference) / (abs(reference) if reference else 1)
    if error > tolerance:
        raise RuntimeError(f'{test} {quantity}: got {computed:.10g}, expected {reference:.10g}')
    return dict(test=test, quantity=quantity, units=units, computed=float(computed),
                reference=float(reference), error=float(error))


def beam(length, count, axis=(1, 0, 0), force=None, line_load=None, fixed=None):
    nodes = np.linspace(0, length, count + 1)[:, None] * axis
    edges = np.column_stack((np.arange(count), np.arange(1, count + 1)))
    tip = 6 * count
    if fixed is None:
        fixed = [0, 1, 2, 3, tip + 1, tip + 2]
    loads = np.zeros(6 * (count + 1))
    if force is not None:
        loads[tip:] = force
    distributed = None if line_load is None else np.broadcast_to(line_load, (count, 3))
    frame = Frame(nodes, edges, fixed, line_loads=distributed, point_loads=loads)
    data = frame.elements()
    scale = np.ones(count)
    return frame, data, scale, frame.state(data, scale)


def verify_structure(bridge):
    rows = []
    def record(*args):
        rows.append(reference_row(*args))

    record('V1', 'Team 2D cantilever tip deflection', 'mm',
           -1000 * solve_cantilever(1, E, 0.02, 0.016, -20, 4), 7.18857)
    length = 2.0
    load = 1000.0
    torque = 25.0
    for axis, rotation, sign in ((1, 5, 1), (2, 4, -1)):
        tip_load = np.zeros(6)
        tip_load[axis] = load
        tip_load[3] = torque
        _, _, _, state = beam(length, 4, force=tip_load, fixed=list(range(6)))
        tip = state.displacement[-6:]
        record('V1', f'3D cantilever translation, axis {axis}', 'mm',
               1000 * tip[axis], 1000 * load * length**3 / (3 * E * INERTIA))
        record('V1', f'3D cantilever tip slope, axis {axis}', 'mrad',
               1000 * sign * tip[rotation], 1000 * load * length**2 / (2 * E * INERTIA))
        if axis == 1:
            record('V1', '3D cantilever twist', 'mrad',
                   1000 * tip[3], 1000 * torque * length / (2 * G * INERTIA))

    count = 8
    axis = np.array([2, -1, 2]) / 3
    direction = np.array([1, 2, 0]) / np.sqrt(5)
    uniform = 400.0
    exact_mm = 1000 * 5 * uniform * length**4 / (384 * E * INERTIA)
    _, _, _, state = beam(length, count, line_load=[0, uniform, 0])
    record('V2', 'Uniform load, simply supported midspan', 'mm',
           1000 * state.displacement.reshape(-1, 6)[count // 2, 1], exact_mm)
    fixed = [0, 1, 2, 3, 6 * count, 6 * count + 1, 6 * count + 2]
    _, _, _, state = beam(length, count, axis, line_load=direction * uniform, fixed=fixed)
    record('V2', 'Rotated midspan displacement projected onto the load', 'mm',
           1000 * np.dot(state.displacement.reshape(-1, 6)[count // 2, :3], direction), exact_mm)
    single, _, _, state = beam(length, 1, line_load=[0, 0, -uniform])
    controls = deck_control_map(single.nodes, single.edges) @ state.displacement
    # The one-element Hermite solution has zero endpoint displacement and a quadratic arc.
    record('V2', 'Single-element Hermite peak between deck nodes', 'mm',
           1000 * peak_deck_deflection(controls.reshape(-1, 4)),
           1000 * uniform * length**4 / (96 * E * INERTIA))

    frequency = np.pi / (2 * length**2) * np.sqrt(E * INERTIA / (DENSITY * AREA))
    euler = np.pi**2 * E * INERTIA / length**2
    for count, frequency_tolerance, buckling_tolerance in (
        (1, 0.12, 0.23), (2, 0.005, 0.009), (4, 0.0004, 0.0007), (8, 0.00003, 0.00005),
    ):
        frame, data, x, state = beam(length, count, force=[-load, 0, 0, 0, 0, 0])
        eigenvalues, _ = frame.n_modes(state, frame.mass(data, x), count=1)
        record('V3', f'First simply supported frequency, {count} elements', 'Hz',
               np.sqrt(eigenvalues[0]) / (2 * np.pi), frequency, frequency_tolerance)
        inv, _ = frame.buckling(data, state, count=1)
        record('V4', f'Pinned column buckling load, {count} elements', 'N',
               load / inv[0], euler, buckling_tolerance)
    for check in ('V3', 'V4'):
        errors = [row['error'] for row in rows if row['test'] == check]
        if any(later >= earlier for earlier, later in zip(errors, errors[1:])):
            raise RuntimeError(f'{check} did not converge monotonically under refinement')

    evaluation = bridge.evaluate(bridge.initial, gradient=False)
    frame = bridge.frame
    elements = frame.elements(evaluation.geometry)
    mass = frame.mass(elements, bridge.initial[bridge.owner])
    eigenvalues = eigsh(evaluation.state.stiffness, M=mass, sigma=-10, which='LM',
                        k=8, return_eigenvectors=False, v0=np.linspace(0.5, 1.5, frame.size))
    record('V5', 'Free bridge rigid-body modes', 'count', np.count_nonzero(abs(eigenvalues) < 1e-3), 6)
    state = evaluation.state
    reactions = (state.stiffness @ state.displacement - state.force).reshape(-1, 6)
    weight = DECK_PRESSURE * SPAN * WIDTH + (evaluation.metrics['mass_kg'] - DECK_MASS) * GRAVITY
    record('V5', 'Supported bridge vertical reaction sum', 'N', reactions[:, 2].sum(), weight)
    # Force times its spanwise arm, about the left bearing line.
    overturning = -np.cross(evaluation.geometry, state.force.reshape(-1, 6)[:, :3])[:, 1].sum()
    overturning -= state.force.reshape(-1, 6)[:, 4].sum()
    reaction_moment = np.cross(evaluation.geometry, reactions[:, :3])[:, 1].sum() + reactions[:, 4].sum()
    record('V5', 'Supported bridge transverse moment balance', 'N·m', reaction_moment, overturning)
    return rows


def outputs(evaluation):
    return np.r_[evaluation.objective, evaluation.constraints]


def verify_gradients(bridge):
    baseline = bridge.initial
    start = perf_counter()
    full = bridge.evaluate(baseline)
    adjoint_seconds = perf_counter() - start
    jacobian = np.vstack((full.objective_gradient, full.jacobian))
    steps = np.array([3e-2, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6])
    rng = np.random.default_rng(24)
    radius_vectors = np.c_[rng.normal(size=(3, bridge.count)), np.zeros((3, 2))]
    mixed = rng.normal(size=(1, len(baseline)))
    mixed[0, -2:] = [2.0, 1.5]
    directions = np.vstack((radius_vectors, np.eye(len(baseline))[-2:], mixed))
    labels = ['Radii 1', 'Radii 2', 'Radii 3', 'Portal height', 'Camber', 'Mixed']
    names = ['Mass', *RESPONSES, 'Member slenderness (worst error)']
    curves = []
    rows = []

    def central(delta):
        plus = bridge.evaluate(baseline + delta, gradient=False)
        minus = bridge.evaluate(baseline - delta, gradient=False)
        return (outputs(plus) - outputs(minus)) / 2

    for label, vector in zip(labels, directions):
        vector /= np.linalg.norm(vector)
        expected = jacobian @ vector
        approximations = np.array([central(step * vector) / step for step in steps])
        errors = abs(approximations - expected)
        normalized_errors = errors / np.maximum(1e-5, abs(expected))
        curves.append({'label': label, 'errors': np.max(errors, axis=1).tolist()})
        best = np.argmin(normalized_errors, axis=0)
        at_best = normalized_errors[best, np.arange(len(expected))]
        if at_best.max() > 2e-4:
            failure = int(np.argmax(at_best))
            raise RuntimeError(f'V6 {label}, component {failure} gradient error {at_best[failure]:.3g}')
        worst_slenderness = 6 + np.argmax(at_best[6:])
        for name, component in zip(names, [0, 1, 2, 3, 4, 5, worst_slenderness]):
            offset = best[component]
            rows.append(dict(direction=label, response=name, adjoint=float(expected[component]),
                             central=float(approximations[offset, component]),
                             error=float(at_best[component]), step=float(steps[offset])))

    # Time a genuine full finite-difference Jacobian and compare it to the adjoint.
    start = perf_counter()
    coordinate_step = 1e-4
    finite = np.column_stack([central(coordinate_step * axis) / coordinate_step
                              for axis in np.eye(len(baseline))])
    central_seconds = perf_counter() - start
    max_absolute = float(np.max(abs(finite - jacobian)))
    if max_absolute > 3e-5:
        raise RuntimeError(f'V6 full Jacobian differs by {max_absolute:.3g}')
    return {'checks': rows, 'steps': steps.tolist(), 'curves': curves,
            'adjoint_seconds': adjoint_seconds, 'central_seconds': central_seconds,
            'finite_solves': 2 * len(baseline), 'max_absolute_jacobian_error': max_absolute}
