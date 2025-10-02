WHITE: tuple[float, float, float] = (1, 1, 1)
YELLOW: tuple[float, float, float] = (1, 1, 0)
BLUE: tuple[float, float, float] = (0, 0, 1)
GREEN: tuple[float, float, float] = (0, 1, 0)
ORANGE: tuple[float, float, float] = (1, 0.5, 0)
RED: tuple[float, float, float] = (1, 0, 0)
BLACK: tuple[float, float, float] = (0, 0, 0)

color_list: list[tuple[float, float, float]] = [
    WHITE, YELLOW, RED, GREEN, ORANGE, BLUE,
]

# Defines the order associated with the set of centers
# (not very useful except for display)
center_list: list[str] = [
    'U', 'D', 'R',
    'F', 'L', 'B',
]
# Defines the order associated with the set of corners
corner_list: list[str] = [
    'URF', 'UFL', 'ULB', 'UBR',
    'DFR', 'DLF', 'DBL', 'DRB',
]
# Defines the order associated with the set of edges
edge_list: list[str] = [
    'UR', 'UF', 'UL',
    'UB', 'DR', 'DF',
    'DL', 'DB', 'FR',
    'FL', 'BL', 'BR',
]

# List of factorials from 11 to 1, we have fact[i] = i!
fact: list[int] = [
    1, 1, 2, 6, 24, 120, 720,
    5040, 40320, 362880, 3628800, 39916800,
]

# Definition of permutations for each move
# referenced respectively by edge_list and corner_list
edge_permutations: dict[str, list[int]] = {
    'U': [3, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11],
    'D': [0, 1, 2, 3, 5, 6, 7, 4, 8, 9, 10, 11],
    'F': [0, 9, 2, 3, 4, 8, 6, 7, 1, 5, 10, 11],
    'B': [0, 1, 2, 11, 4, 5, 6, 10, 8, 9, 3, 7],
    'L': [0, 1, 10, 3, 4, 5, 9, 7, 8, 2, 6, 11],
    'R': [8, 1, 2, 3, 11, 5, 6, 7, 4, 9, 10, 0],
}

corner_permutations: dict[str, list[int]] = {
    'U': [3, 0, 1, 2, 4, 5, 6, 7],
    'D': [0, 1, 2, 3, 5, 6, 7, 4],
    'F': [1, 5, 2, 3, 0, 4, 6, 7],
    'B': [0, 1, 3, 7, 4, 5, 2, 6],
    'L': [0, 2, 6, 3, 4, 1, 5, 7],
    'R': [4, 1, 2, 0, 7, 5, 6, 3],
}

edge_orientations: dict[str, list[int]] = {
    'U': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'D': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'F': [0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0],
    'B': [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1],
    'L': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'R': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}

corner_orientations: dict[str, list[int]] = {
    'U': [0, 0, 0, 0, 0, 0, 0, 0],
    'D': [0, 0, 0, 0, 0, 0, 0, 0],
    'F': [1, 2, 0, 0, 2, 1, 0, 0],
    'B': [0, 0, 1, 2, 0, 0, 2, 1],
    'L': [0, 1, 2, 0, 0, 2, 1, 0],
    'R': [2, 0, 0, 1, 1, 0, 0, 2],
}

# Table giving the rotation axis based on the rotation performed,
# if we rotate counterclockwise we need to multiply the axis by -1
rotation_axis: dict[str, tuple[int, int, int]] = {
    'U': (0, -1, 0),
    'F': (0, 0, -1),
    'R': (-1, 0, 0),
    'D': (0, 1, 0),
    'B': (0, 0, 1),
    'L': (1, 0, 0),
}

# Table of coordinates to draw the surface that will hide
# the interior of the cube during face rotation
hide_coords: dict[str, list[tuple[int, int, int]]] = {
    'U': [(-3, 1, -3), (3, 1, -3), (3, 1, 3), (-3, 1, 3)],
    'D': [(-3, -1, -3), (3, -1, -3), (3, -1, 3), (-3, -1, 3)],
    'F': [(-3, 3, 1), (-3, -3, 1), (3, -3, 1), (3, 3, 1)],
    'B': [(-3, 3, -1), (-3, -3, -1), (3, -3, -1), (3, 3, -1)],
    'L': [(-1, 3, -3), (-1, -3, -3), (-1, -3, 3), (-1, 3, 3)],
    'R': [(1, 3, -3), (1, -3, -3), (1, -3, 3), (1, 3, 3)],
}

# List of points to adjust the texture on the surface
tex_map: list[tuple[int, int]] = [
    (0, 0),
    (0, 1),
    (1, 1),
    (1, 0),
]

# Coordinates of the 8 points to draw a cube in space
s: list[tuple[int, int, int]] = [
    (1, 1, 1),
    (-1, 1, 1),
    (-1, 1, -1),
    (1, 1, -1),
    (1, -1, 1),
    (-1, -1, 1),
    (-1, -1, -1),
    (1, -1, -1),
]


# Function to change the size of the cube
def vertices(x: float) -> list[list[float]]:
    return [
        list(map(float.__mul__, [x] * 3, point))
        for point in s
    ]


indices: list[tuple[int, int, int, int]] = [
    (0, 1, 2, 3),
    (4, 5, 6, 7),
    (7, 4, 0, 3),
    (4, 5, 1, 0),
    (5, 6, 2, 1),
    (6, 7, 3, 2),
]

position_list: list[str] = [
    'F', 'L', 'D', 'U', 'R', 'B',
    'DR', 'UB', 'FL', 'BL',
    'DF', 'UR', 'UL', 'DB',
    'DL', 'UF', 'FR', 'BR',
    'UBR', 'UFR', 'UFL', 'DFR',
    'DFL', 'UBL', 'DBL', 'DBR',
]

center_positions_table: list[tuple[int, int, int]] = [
    (0, 2, 0), (0, -2, 0), (2, 0, 0),
    (0, 0, 2), (-2, 0, 0), (0, 0, -2),
]

edge_positions_table: list[tuple[int, int, int]] = [
    (2, 2, 0), (0, 2, 2), (-2, 2, 0), (0, 2, -2),
    (2, -2, 0), (0, -2, 2), (-2, -2, 0), (0, -2, -2),
    (2, 0, 2), (-2, 0, 2), (-2, 0, -2), (2, 0, -2),
]

corner_positions_table: list[tuple[int, int, int]] = [
    (2, 2, 2), (-2, 2, 2), (-2, 2, -2), (2, 2, -2),
    (2, -2, 2), (-2, -2, 2), (-2, -2, -2), (2, -2, -2),
]

center_colors_table: list[list[int]] = [
    [0], [1], [2], [3], [4], [5],
]

edge_colors_table: list[list[int]] = [
    [0, 2], [0, 3], [0, 4], [0, 5],
    [1, 2], [1, 3], [1, 4], [1, 5],
    [3, 2], [3, 4], [5, 4], [5, 2],
]

corner_colors_table: list[list[int]] = [
    [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2],
    [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5],
]

edge_orientation_axis_table: list[tuple[int, int, int]] = [
    (1, 1, 0), (0, 1, 1), (-1, 1, 0), (0, 1, -1),
    (1, -1, 0), (0, -1, 1), (-1, -1, 0), (0, -1, -1),
    (1, 0, 1), (-1, 0, 1), (-1, 0, -1), (1, 0, -1),
]

corner_orientation_axis_table: list[tuple[int, int, int]] = [
    (1, 1, 1), (-1, 1, 1), (-1, 1, -1), (1, 1, -1),
    (1, -1, 1), (-1, -1, 1), (-1, -1, -1), (1, -1, -1),
]

# Table of facelets that should display a color for each piece
colors_table: dict[str, list[int]] = {
    'U': [0], 'D': [1], 'R': [2],
    'F': [3], 'L': [4], 'B': [5],
    'UR': [0, 2], 'UF': [0, 3], 'UL': [0, 4], 'UB': [0, 5],
    'DR': [1, 2], 'DF': [1, 3], 'DL': [1, 4], 'DB': [1, 5],
    'FR': [3, 2], 'FL': [3, 4], 'BL': [5, 4], 'BR': [5, 2],
    'URF': [0, 2, 3], 'UFL': [0, 3, 4],
    'ULB': [0, 4, 5], 'UBR': [0, 5, 2],
    'DFR': [1, 3, 2], 'DLF': [1, 4, 3],
    'DBL': [1, 5, 4], 'DRB': [1, 2, 5],
}

# Table of (dX, dY, dZ)
# Translation parameters to position the pieces in
# space relative to the center of the cube
positions_table: dict[str, tuple[int, int, int]] = {
    '': (0, 0, 0),
    'U': (0, 2, 0), 'D': (0, -2, 0), 'F': (0, 0, 2),
    'B': (0, 0, -2), 'L': (-2, 0, 0), 'R': (2, 0, 0),
    'UF': (0, 2, 2), 'UB': (0, 2, -2), 'UL': (-2, 2, 0),
    'UR': (2, 2, 0), 'DF': (0, -2, 2), 'DB': (0, -2, -2),
    'DL': (-2, -2, 0), 'DR': (2, -2, 0), 'FL': (-2, 0, 2),
    'FR': (2, 0, 2), 'BL': (-2, 0, -2), 'BR': (2, 0, -2),
    'UFL': (-2, 2, 2), 'URF': (2, 2, 2),
    'ULB': (-2, 2, -2), 'UBR': (2, 2, -2),
    'DLF': (-2, -2, 2), 'DFR': (2, -2, 2),
    'DBL': (-2, -2, -2), 'DRB': (2, -2, -2),
}
