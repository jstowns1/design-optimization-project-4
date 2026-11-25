"""V1: linear 2D frame analysis of a circular tube cantilever."""

from math import pi


def solve_linear_system(matrix, right_hand_side):
    """Solve a square linear system using Gauss–Jordan elimination with partial pivoting."""
    size = len(right_hand_side)
    augmented = [row[:] + [value] for row, value in zip(matrix, right_hand_side)]

    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if augmented[pivot][column] == 0:
            raise ValueError("The stiffness matrix is singular.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]

        pivot_value = augmented[column][column]
        for entry in range(column, size + 1):
            augmented[column][entry] /= pivot_value

        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            for entry in range(column, size + 1):
                augmented[row][entry] -= factor * augmented[column][entry]

    return [augmented[row][size] for row in range(size)]


def frame_element_stiffness(length, axial_rigidity, bending_rigidity):
    """Return the stiffness of a horizontal Euler–Bernoulli frame element."""
    axial = axial_rigidity / length
    transverse = 12 * bending_rigidity / length**3
    coupling = 6 * bending_rigidity / length**2
    rotation = 4 * bending_rigidity / length
    rotation_cross = 2 * bending_rigidity / length

    # Each node has horizontal displacement, vertical displacement, and rotation.
    return [
        [axial, 0, 0, -axial, 0, 0],
        [0, transverse, coupling, 0, -transverse, coupling],
        [0, coupling, rotation, 0, -coupling, rotation_cross],
        [-axial, 0, 0, axial, 0, 0],
        [0, -transverse, -coupling, 0, transverse, -coupling],
        [0, coupling, rotation_cross, 0, -coupling, rotation],
    ]


def solve_cantilever(length, modulus, outer_diameter, inner_diameter,
                     tip_load, element_count):
    """Return vertical tip displacement in metres, with positive y upward."""
    area = pi / 4 * (outer_diameter**2 - inner_diameter**2)
    second_moment = pi / 64 * (outer_diameter**4 - inner_diameter**4)
    element_stiffness = frame_element_stiffness(
        length / element_count, modulus * area, modulus * second_moment
    )

    dofs_per_node = 3
    dof_count = dofs_per_node * (element_count + 1)
    stiffness = [[0.0] * dof_count for _ in range(dof_count)]
    for element in range(element_count):
        start = dofs_per_node * element
        for local_row, element_row in enumerate(element_stiffness):
            global_row = stiffness[start + local_row]
            for local_column, entry in enumerate(element_row):
                global_row[start + local_column] += entry

    tip_vertical_dof = dofs_per_node * element_count + 1
    force = [0.0] * dof_count
    force[tip_vertical_dof] = tip_load

    # The left node's two translations and rotation are fixed at zero.
    free_stiffness = [row[dofs_per_node:] for row in stiffness[dofs_per_node:]]
    displacement = [0.0] * dof_count
    displacement[dofs_per_node:] = solve_linear_system(
        free_stiffness, force[dofs_per_node:]
    )
    return displacement[tip_vertical_dof]


def main():
    tip_displacement_m = solve_cantilever(
        length=1.00,
        modulus=200e9,
        outer_diameter=0.020,
        inner_diameter=0.016,
        tip_load=-20.0,
        element_count=4,
    )

    hand_magnitude_mm = 7.18857
    tip_magnitude_mm = abs(tip_displacement_m) * 1000
    percent_error = 100 * abs(tip_magnitude_mm - hand_magnitude_mm) / hand_magnitude_mm
    if tip_displacement_m < 0:
        direction = " downward"
    elif tip_displacement_m > 0:
        direction = " upward"
    else:
        direction = ""

    print(f"Solver tip displacement: {tip_magnitude_mm:.8f} mm{direction}")
    print(f"Hand-calculated magnitude: {hand_magnitude_mm:.5f} mm")
    print(f"Percent error: {percent_error:.8f} %")

    if tip_displacement_m >= 0 or round(tip_magnitude_mm, 5) != hand_magnitude_mm:
        raise SystemExit("V1 failed: expected downward deflection matching the hand value to five decimal places in mm.")


if __name__ == "__main__":
    main()
