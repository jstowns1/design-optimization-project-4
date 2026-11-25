"""Sizing and shape model for the 15 m Pratt footbridge (deck option D2)."""

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix

from frame3d import AREA, DENSITY, GRAVITY, INERTIA, REFERENCE_RADIUS, Frame, apply, transpose


SPAN = 15.0
WIDTH = 3.0
PLATE = 0.008
DECK_PRESSURE = 5000 + DENSITY * GRAVITY * PLATE
DECK_MASS = DENSITY * PLATE * WIDTH * SPAN
STATIC_LIMIT = 160e6
ENDURANCE = 0.7 * 86.2e6
ULTIMATE = 460e6
FATIGUE_LIMIT = 1 / (1 / ENDURANCE + 1 / ULTIMATE)
DEFLECTION_LIMIT = SPAN / 400
FREQUENCY_LIMIT = 3.0
BUCKLING_LIMIT = 3.0
SLENDERNESS_LIMIT = 200.0
GYRATION = np.sqrt(INERTIA / AREA)
MASS_SCALE = 10000.0
RESPONSES = ('Static stress', 'Goodman fatigue', 'Deck deflection', 'Frequency', 'Buckling')


def ks(values, sharpness):
    """Conservative smooth maximum and its weights."""
    peak = np.max(values)
    exponential = np.exp(sharpness * (values - peak))
    total = exponential.sum()
    return peak + np.log(total) / sharpness, exponential / total


def modal_vectors(frame, vectors):
    """Expand constrained modes and gather their element degrees of freedom."""
    return frame.expand(vectors)[frame.dofs]


def mode_energy(vectors, matrices):
    return np.einsum('eik,eij,ejk->ek', vectors, matrices, vectors, optimize=True)


def deck_control_map(nodes, edges):
    """Map nodal DOFs to cubic Bézier controls for vertical deck deflection."""
    # The vertical Hermite slope times length is (theta × end-to-end vector).z.
    offset = nodes[edges[:, 1]] - nodes[edges[:, 0]]
    indices = 6 * edges[:, [0, 0, 1, 1], None] + np.array([2, 3, 4])
    coefficients = np.zeros(indices.shape)
    coefficients[:, :, 0] = 1
    coefficients[:, 1, 1:] = offset[:, [1, 0]] * [1 / 3, -1 / 3]
    coefficients[:, 2, 1:] = -coefficients[:, 1, 1:]
    rows = np.repeat(np.arange(4 * len(edges)), 3)
    return coo_matrix((coefficients.ravel(), (rows, indices.ravel())),
                      shape=(4 * len(edges), 6 * len(nodes))).tocsr()


def peak_deck_deflection(controls):
    """Return the largest absolute value on the recovered cubic deck curves."""
    peak = np.abs(controls[:, [0, 3]]).max()
    for a, b, c, d in controls:
        polynomial = [a, 3 * (b - a), 3 * (a - 2 * b + c), -a + 3 * b - 3 * c + d]
        derivative = np.polynomial.polynomial.polyder(polynomial)
        for root in np.polynomial.polynomial.polyroots(derivative):
            if np.isreal(root) and 0 < root.real < 1:
                peak = max(peak, abs(np.polynomial.polynomial.polyval(root.real, polynomial)))
    return peak


@dataclass
class Evaluation:
    objective: float
    constraints: np.ndarray
    metrics: dict
    geometry: np.ndarray
    state: object
    stress: np.ndarray
    mode: np.ndarray
    objective_gradient: np.ndarray | None = None
    jacobian: np.ndarray | None = None


class Bridge:
    """Continuous radius per physical member and two top-chord height parameters."""

    def __init__(self, subdivisions=2):
        bays = 6
        bay = SPAN / bays
        spacing = WIDTH / 4
        base = []
        motion = []
        deck = {}
        top = {}
        for station in range(bays + 1):
            x = station * bay
            for line in range(5):
                deck[station, line] = len(base)
                base.append([x, line * spacing - WIDTH / 2, 0])
                motion.append([0.0, 0.0])
            for side in (0, 4):
                top[station, side] = len(base)
                base.append([x, side * spacing - WIDTH / 2, 0])
                motion.append([1.0, 4 * (x / SPAN) * (1 - x / SPAN)])

        members = []
        labels = []
        tributary = []
        deck_nodes = set(deck.values())

        def member(a, b, label, deck_width=0.0):
            members.append((a, b))
            labels.append(label)
            tributary.append(deck_width)

        for station in range(bays + 1):
            for side in (0, 4):
                member(deck[station, side], top[station, side], 'Vertical')
            member(top[station, 0], top[station, 4], 'Overhead cross member')
            for line in range(4):
                member(deck[station, line], deck[station, line + 1], 'Floor beam')
            if station == bays:
                continue
            for line in range(5):
                edge = line in (0, 4)
                member(deck[station, line], deck[station + 1, line],
                       'Bottom chord' if edge else 'Stringer', spacing / 2 if edge else spacing)
            for side in (0, 4):
                member(top[station, side], top[station + 1, side], 'Top chord')
                inner_station = station + (station < bays / 2)
                outer_station = 2 * station + 1 - inner_station
                member(top[outer_station, side], deck[inner_station, side], 'Pratt diagonal')
            start_side = 0 if station < bays / 2 else 4
            member(top[station, start_side], top[station + 1, 4 - start_side], 'Lateral brace')

        self.members = np.asarray(members)
        self.labels = labels
        self.count = len(members)
        self.owner = np.repeat(np.arange(self.count), subdivisions)
        edges = []
        for index, (a, b) in enumerate(members):
            previous = a
            for segment in range(1, subdivisions + 1):
                next_node = b
                if segment < subdivisions:
                    fraction = segment / subdivisions
                    next_node = len(base)
                    base.append((1 - fraction) * np.asarray(base[a]) + fraction * np.asarray(base[b]))
                    motion.append((1 - fraction) * np.asarray(motion[a]) + fraction * np.asarray(motion[b]))
                    if labels[index] in ('Bottom chord', 'Stringer', 'Floor beam'):
                        deck_nodes.add(next_node)
                edges.append((previous, next_node))
                previous = next_node

        self.base = np.asarray(base, dtype=float)
        self.motion = np.asarray(motion, dtype=float)
        self.bounds = [(0.010 / REFERENCE_RADIUS, 0.150 / REFERENCE_RADIUS)] * self.count
        # Shape variables are metres, with a nonnegative rise above the portal height.
        self.bounds += [(2.45, 3.4), (0.0, 0.65)]
        self.initial = np.r_[np.full(self.count, 0.075 / REFERENCE_RADIUS), 2.65, 0.25]
        initial_nodes = self.coordinates(self.initial[-2:])
        left = [6 * deck[0, line] + axis for line in range(5) for axis in (0, 1, 2)]
        right = [6 * deck[bays, line] + axis for line in range(5) for axis in (1, 2)]
        # Interior nodes of the two end floor beams also lie on the bearing lines.
        for node in deck_nodes - set(deck.values()):
            coordinate = initial_nodes[node, 0]
            if coordinate == 0:
                left.extend(6 * node + axis for axis in (0, 1, 2))
            if coordinate == SPAN:
                right.extend(6 * node + axis for axis in (1, 2))
        edges = np.asarray(edges)
        widths = np.asarray(tributary)[self.owner]
        lengths = np.linalg.norm(initial_nodes[edges[:, 1]] - initial_nodes[edges[:, 0]], axis=1)
        nodal_mass = np.zeros(len(base))
        np.add.at(nodal_mass, edges.ravel(), np.repeat(DENSITY * PLATE * widths * lengths / 2, 2))
        line_loads = np.zeros((len(edges), 3))
        line_loads[:, 2] = -DECK_PRESSURE * widths
        self.frame = Frame(initial_nodes, edges, left + right, line_loads=line_loads,
                           nodal_mass=nodal_mass, gravity=GRAVITY)
        # Only the top-chord coordinates depend on the shape design.
        deck_edges = np.isin(np.asarray(labels)[self.owner], ('Bottom chord', 'Stringer', 'Floor beam'))
        self.deck_controls = deck_control_map(initial_nodes, edges[deck_edges])

    def coordinates(self, shape):
        nodes = self.base.astype(np.result_type(shape, float), copy=True)
        nodes[:, 2] += self.motion @ shape
        return nodes

    def sum_members(self, quantities):
        return np.bincount(self.owner, weights=quantities, minlength=self.count)

    def evaluate(self, design, gradient=True):
        frame = self.frame
        nodes = self.coordinates(design[-2:])
        elements = frame.elements(nodes)
        x = design[self.owner]
        state = frame.state(elements, x)
        length = self.sum_members(elements.length)
        member_mass = DENSITY * AREA * design[:self.count]**2 * length
        mass = DECK_MASS + member_mass.sum()
        slenderness = length / (GYRATION * design[:self.count])

        actions = state.actions.reshape(-1, 2, 6)
        # The very small smoothings (1 N, 1e-4 Nm) regularize derivatives at zero force.
        area = AREA * x[:, None]**2
        outer_fiber = REFERENCE_RADIUS / INERTIA / x[:, None]**3
        axial_force = np.sqrt(actions[:, :, 0]**2 + 1)
        bending_moment = np.sqrt(np.sum(actions[:, :, 4:6]**2, axis=2) + 1e-8)
        axial_stress = axial_force / area
        bending_stress = bending_moment * outer_fiber
        shear = actions[:, :, 3] * outer_fiber / 2
        normal = axial_stress + bending_stress
        stress = np.sqrt(normal**2 + 3 * shear**2)
        physical_stress = np.sqrt((np.abs(actions[:, :, 0]) / area +
                                   np.linalg.norm(actions[:, :, 4:6], axis=2) * outer_fiber)**2 + 3 * shear**2)
        constraints = []
        stress_weights = []
        for limit in (STATIC_LIMIT, FATIGUE_LIMIT):
            value, weights = ks(stress / limit, 90)
            constraints.append(value - 1)
            stress_weights.append(weights / limit)

        deck_controls = self.deck_controls @ state.displacement
        deck = deck_controls / DEFLECTION_LIMIT
        # The curve is inside the convex hull of its controls, including between nodes.
        value, weights = ks(np.r_[deck, -deck], 120)
        constraints.append(value - 1)
        up, down = np.split(weights, 2)
        deck_gradient = (up - down) / DEFLECTION_LIMIT

        eig, modes = frame.n_modes(state, frame.mass(elements, x))
        frequencies = np.sqrt(eig) / (2 * np.pi)
        frequency_ratios = FREQUENCY_LIMIT / frequencies
        value, weights = ks(frequency_ratios, 90)
        constraints.append(value - 1)
        frequency_weights = -weights * frequency_ratios / (2 * eig)

        inv_buckling, buckling_modes = frame.buckling(elements, state)
        value, weights = ks(BUCKLING_LIMIT * inv_buckling, 90)
        constraints.append(value - 1)
        buckling_weights = BUCKLING_LIMIT * weights
        peak = physical_stress.max()
        metrics = {
            'mass_kg': float(mass), 'stress_mpa': float(peak / 1e6),
            'goodman': float(2 * FATIGUE_LIMIT / peak),
            'deflection_mm': 1000 * float(peak_deck_deflection(deck_controls.reshape(-1, 4))),
            'frequency_hz': float(frequencies.min()), 'buckling_factor': float(1 / inv_buckling.max()),
            'slenderness': float(slenderness.max()),
        }
        controlling_mode = frame.expand(buckling_modes[:, np.argmax(inv_buckling)])
        result = Evaluation(mass / MASS_SCALE,
                            np.r_[constraints, slenderness / SLENDERNESS_LIMIT - 1],
                            metrics, nodes, state, physical_stress, controlling_mode)
        if not gradient:
            return result

        # Partial response derivatives at fixed nodal state.
        stress_action = np.zeros_like(actions)
        normal_factor = normal / stress
        stress_action[:, :, 0] = normal_factor * actions[:, :, 0] / (axial_force * area)
        stress_action[:, :, 3] = 3 * shear * outer_fiber / (2 * stress)
        stress_action[:, :, 4:6] = ((normal_factor * outer_fiber / bending_moment)[:, :, None]
                                    * actions[:, :, 4:6])
        stress_radius = -(normal_factor * (2 * axial_stress + 3 * bending_stress)
                          + 9 * shear**2 / stress) / x[:, None]

        action_gradient = np.zeros((len(x), 12, 5))
        for index, weights in enumerate(stress_weights):
            action_gradient[:, :, index] = (weights[:, :, None] * stress_action).reshape(-1, 12)
        vibration_phi = modal_vectors(frame, modes)
        buckling_phi = modal_vectors(frame, buckling_modes)
        transform = elements.transform
        local_psi = transform @ buckling_phi
        buckling_axial = -(mode_energy(local_psi, elements.geometric) @ buckling_weights)
        action_gradient[:, 0, 4] = -buckling_axial / 2
        action_gradient[:, 6, 4] = buckling_axial / 2
        axial_prestress = (state.actions[:, 6] - state.actions[:, 0]) / 2

        displacement_gradient = np.column_stack([
            frame.vector(apply(transpose(state.action_operator), action_gradient[:, :, index]))
            for index in range(5)
        ])
        displacement_gradient[:, 2] = self.deck_controls.T @ deck_gradient
        adjoint = frame.expand(state.factor.solve(-displacement_gradient[frame.free], trans='T'))
        local_adjoint = adjoint[frame.dofs]
        u = state.displacement[frame.dofs]

        def differentiate(action_rate, residual_rate, elastic_rate, mass_rate, geometric_rate=None):
            partial = np.einsum('eik,ei->ek', action_gradient, action_rate)
            partial += np.einsum('eik,ei->ek', local_adjoint, residual_rate)
            partial[:, 3] += ((mode_energy(vibration_phi, elastic_rate) -
                               eig * mode_energy(vibration_phi, mass_rate)) @ frequency_weights)
            partial[:, 4] -= (mode_energy(buckling_phi, elastic_rate) @
                               (inv_buckling * buckling_weights))
            if geometric_rate is not None:
                partial[:, 4] -= axial_prestress * (mode_energy(buckling_phi, geometric_rate) @ buckling_weights)
            return partial

        radius2 = 2 * x[:, None, None]
        radius4 = 4 * x[:, None, None]**3
        elastic_rate = (elements.axial * radius2 + elements.bending * radius4) @ transform
        mass_rate = elements.mass_area * radius2 + elements.mass_polar * radius4
        action_rate = apply(elastic_rate, u) - elements.weight * radius2[:, :, 0]
        inverse = transpose(transform)
        radius_partial = differentiate(action_rate, apply(inverse, action_rate), inverse @ elastic_rate,
                                       inverse @ mass_rate @ transform)
        for index, weights in enumerate(stress_weights):
            radius_partial[:, index] += np.sum(weights * stress_radius, axis=1)

        variable_count = len(design)
        jacobian = np.zeros((5 + self.count, variable_count))
        for index in range(5):
            jacobian[index, :self.count] = self.sum_members(radius_partial[:, index])
        diagonal = np.arange(self.count)
        jacobian[5 + diagonal, diagonal] = -slenderness / (SLENDERNESS_LIMIT * design[:self.count])
        mass_gradient = np.zeros(variable_count)
        mass_gradient[:self.count] = 2 * member_mass / design[:self.count]

        # Complex-step only the local geometry maps, holding the FE state fixed.
        step = 1e-28
        r2 = x[:, None, None]**2
        for index in range(2):
            shape = design[-2:].astype(complex)
            shape[index] += 1j * step
            perturbed = frame.elements(self.coordinates(shape))
            T = perturbed.transform
            TT = transpose(T)
            operator = (perturbed.axial * r2 + perturbed.bending * r2**2) @ T
            load = perturbed.applied + perturbed.weight * r2[:, :, 0]
            actions_perturbed = apply(operator, u) - load
            local_mass = perturbed.mass_area * r2 + perturbed.mass_polar * r2**2
            shape_partial = differentiate(actions_perturbed.imag / step,
                                           apply(TT, actions_perturbed).imag / step,
                                           (TT @ operator).imag / step,
                                           (TT @ local_mass @ T).imag / step,
                                           (TT @ perturbed.geometric @ T).imag / step)
            jacobian[:5, self.count + index] = shape_partial.sum(axis=0)
            length_rate = self.sum_members(perturbed.length.imag / step)
            jacobian[5:, self.count + index] = length_rate / (SLENDERNESS_LIMIT * GYRATION * design[:self.count])
            mass_gradient[self.count + index] = DENSITY * AREA * np.dot(design[:self.count]**2, length_rate)

        result.objective_gradient = mass_gradient / MASS_SCALE
        result.jacobian = jacobian
        return result
