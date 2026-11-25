"""Small-displacement, circular-tube Euler–Bernoulli frame elements in SI units."""

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import LinearOperator, eigsh, splu


E = 200e9
G = E / (2 * (1 + 0.3))
DENSITY = 7850.0
GRAVITY = 9.81
REFERENCE_RADIUS = 0.05
AREA = np.pi * (1 - 0.9**2) * REFERENCE_RADIUS**2
INERTIA = np.pi / 4 * (1 - 0.9**4) * REFERENCE_RADIUS**4


@dataclass
class ElementData:
    length: np.ndarray
    transform: np.ndarray
    axial: np.ndarray
    bending: np.ndarray
    mass_area: np.ndarray
    mass_polar: np.ndarray
    applied: np.ndarray
    weight: np.ndarray
    geometric: np.ndarray


def tube_elements(nodes, edges, reference_axes, line_loads, gravity):
    """Return batches of local matrices and load vectors at the reference radius."""
    axis = nodes[edges[:, 1]] - nodes[edges[:, 0]]
    length = np.sqrt(np.sum(axis**2, axis=1))
    x = axis / length[:, None]
    y = np.cross(reference_axes, x)
    y /= np.sqrt(np.sum(y**2, axis=1))[:, None]
    z = np.cross(x, y)
    rotation = np.stack((x, y, z), axis=1)
    transform = np.zeros((len(edges), 12, 12), dtype=nodes.dtype)
    for offset in (0, 3, 6, 9):
        transform[:, offset:offset + 3, offset:offset + 3] = rotation

    axial, bending, mass_area, mass_polar, geometric = (
        np.zeros_like(transform) for _ in range(5)
    )
    applied, weight = (np.zeros((len(edges), 12), dtype=nodes.dtype) for _ in range(2))
    L = length[:, None, None]
    pair = np.array([[1, -1], [-1, 1]])
    mass_pair = np.array([[2, 1], [1, 2]])
    for offset, rigidity, inertia, elastic, mass in (
        (0, E * AREA, DENSITY * AREA, axial, mass_area),
        (3, G * 2 * INERTIA, DENSITY * 2 * INERTIA, bending, mass_polar),
    ):
        dofs = np.ix_([offset, offset + 6], [offset, offset + 6])
        elastic[:, dofs[0], dofs[1]] = rigidity / L * pair
        mass[:, dofs[0], dofs[1]] = inertia * L / 6 * mass_pair

    # The Hermite rotation degrees of freedom carry dimensions of slope.
    slope = np.stack((np.ones_like(length), length, np.ones_like(length), length), axis=1)
    scale = slope[:, :, None] * slope[:, None, :]
    flexure = E * INERTIA / L**3 * scale * np.array([
        [12, 6, -12, 6], [6, 4, -6, 2], [-12, -6, 12, -6], [6, 2, -6, 4],
    ])
    flexure_mass = DENSITY * AREA * L / 420 * scale * np.array([
        [156, 22, 54, -13], [22, 4, 13, -3], [54, 13, 156, -22], [-13, -3, -22, 4],
    ])
    unit_geometric = scale / (30 * L) * np.array([
        [36, 3, -36, 3], [3, 4, -3, -1], [-36, -3, 36, -3], [3, -1, -3, 4],
    ])
    local_load = np.einsum('eij,ej->ei', rotation, line_loads)
    local_weight = -DENSITY * AREA * gravity * rotation[:, :, 2]
    applied[:, [0, 6]] = local_load[:, :1] * length[:, None] / 2
    weight[:, [0, 6]] = local_weight[:, :1] * length[:, None] / 2
    for component, dofs, signs in (
        (1, [1, 5, 7, 11], np.ones(4)),
        (2, [2, 4, 8, 10], np.array([1, -1, 1, -1])),
    ):
        rows, columns = np.ix_(dofs, dofs)
        signed = signs[:, None] * signs[None, :]
        bending[:, rows, columns] = flexure * signed
        mass_area[:, rows, columns] = flexure_mass * signed
        geometric[:, rows, columns] = unit_geometric * signed
        equivalent = length[:, None] * slope * [0.5, 1 / 12, 0.5, -1 / 12] * signs
        applied[:, dofs] = local_load[:, component:component + 1] * equivalent
        weight[:, dofs] = local_weight[:, component:component + 1] * equivalent
    return ElementData(length, transform, axial, bending, mass_area, mass_polar,
                       applied, weight, geometric)


def transpose(batch):
    return batch.swapaxes(1, 2)


def apply(batch, vectors):
    return np.einsum('eij,ej->ei', batch, vectors)


class Frame:
    """Connectivity, fixed DOFs, and sparse assembly for a 3D frame."""

    def __init__(self, nodes, edges, fixed, line_loads=None, point_loads=None,
                 nodal_mass=None, gravity=0.0):
        self.nodes = np.asarray(nodes, dtype=float)
        self.edges = np.asarray(edges, dtype=int)
        self.size = 6 * len(nodes)
        self.free = np.setdiff1d(np.arange(self.size), fixed)
        starts = 6 * self.edges[:, :, None] + np.arange(6)
        self.dofs = starts.reshape(-1, 12)
        self.rows = np.broadcast_to(self.dofs[:, :, None], (len(edges), 12, 12)).ravel()
        self.columns = np.broadcast_to(self.dofs[:, None, :], (len(edges), 12, 12)).ravel()
        axes = self.nodes[self.edges[:, 1]] - self.nodes[self.edges[:, 0]]
        self.reference_axes = np.tile([0.0, 0.0, 1.0], (len(edges), 1))
        self.reference_axes[np.abs(axes[:, 2]) > 0.9 * np.linalg.norm(axes, axis=1)] = [0, 1, 0]
        self.line_loads = np.zeros((len(edges), 3)) if line_loads is None else line_loads
        self.point_loads = np.zeros(self.size) if point_loads is None else point_loads
        self.gravity = gravity
        mass = np.zeros((len(nodes), 6))
        if nodal_mass is not None:
            mass[:, :3] = np.asarray(nodal_mass)[:, None]
        self.nodal_mass = diags(mass.ravel(), format='csc')

    def elements(self, nodes=None):
        return tube_elements(self.nodes if nodes is None else nodes, self.edges,
                             self.reference_axes, self.line_loads, self.gravity)

    def matrix(self, element_matrices):
        return coo_matrix((element_matrices.ravel(), (self.rows, self.columns)),
                          shape=(self.size, self.size)).tocsc()

    def vector(self, element_vectors):
        out = np.zeros(self.size)
        np.add.at(out, self.dofs, element_vectors)
        return out

    def reduce(self, matrix):
        return matrix[self.free][:, self.free].tocsc()

    def expand(self, values):
        out = np.zeros((self.size, *values.shape[1:]))
        out[self.free] = values
        return out

    def state(self, elements, radius_scale):
        r2 = radius_scale[:, None]**2
        r4 = r2**2
        transform = elements.transform
        inverse = transpose(transform)
        local_k = elements.axial * r2[:, :, None] + elements.bending * r4[:, :, None]
        operator = local_k @ transform
        K = self.matrix(inverse @ operator)
        local_load = elements.applied + elements.weight * r2
        force = self.vector(apply(inverse, local_load)) + self.point_loads
        reduced = self.reduce(K)
        factor = splu(reduced)
        u = self.expand(factor.solve(force[self.free]))
        actions = apply(operator, u[self.dofs]) - local_load
        return State(K, reduced, factor, force, u, actions, operator)

    def mass(self, elements, radius_scale):
        r2 = radius_scale[:, None, None]**2
        local = elements.mass_area * r2 + elements.mass_polar * r2**2
        transform = elements.transform
        return self.matrix(transpose(transform) @ local @ transform) + self.nodal_mass

    def n_modes(self, state, mass, count=6):
        inverse = LinearOperator(state.reduced.shape, matvec=state.factor.solve, dtype=float)
        return eigsh(state.reduced, M=self.reduce(mass), sigma=0.0, which='LM', k=count,
                     OPinv=inverse, v0=np.linspace(0.5, 1.5, len(self.free)), tol=1e-10)

    def buckling(self, elements, state, count=6):
        axial_force = (state.actions[:, 6] - state.actions[:, 0]) / 2
        transform = elements.transform
        unit = transpose(transform) @ elements.geometric @ transform
        negative_geometric = self.reduce(self.matrix(-axial_force[:, None, None] * unit))
        inverse = LinearOperator(state.reduced.shape, matvec=state.factor.solve, dtype=float)
        return eigsh(negative_geometric, M=state.reduced, Minv=inverse, which='LA', k=count,
                     v0=np.linspace(0.5, 1.5, len(self.free)), tol=1e-10)


@dataclass
class State:
    stiffness: object
    reduced: object
    factor: object
    force: np.ndarray
    displacement: np.ndarray
    actions: np.ndarray
    action_operator: np.ndarray
