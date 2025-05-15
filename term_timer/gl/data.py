BLANC = (1, 1, 1)
JAUNE = (1, 1, 0)
BLEU = (0, 0, 1)
VERT = (0, 1, 0)
ORANGE = (1, 0.5, 0)
ROUGE = (1, 0, 0)
NOIR = (0, 0, 0)

liste_couleurs = [BLANC, JAUNE, ROUGE, VERT, ORANGE, BLEU]

# Définit l'ordre associé à l'ensemble des centres
# (peu utile sauf pour l'affichage)
liste_centres = [
    'U', 'D', 'R',
    'F', 'L', 'B',
]
# Définit l'ordre associé à l'ensemble des coins
liste_coins = [
    'URF', 'UFL', 'ULB', 'UBR',
    'DFR', 'DLF', 'DBL', 'DRB',
]
# Définit l'ordre associé à l'ensemble des arêtes
liste_aretes = [
    'UR', 'UF', 'UL',
    'UB', 'DR', 'DF',
    'DL', 'DB', 'FR',
    'FL', 'BL', 'BR',
]

# Liste des factorielles de 11 à 1, on a alors fact[i] = i!
fact = [1, 1, 2, 6, 24, 120, 720, 5040, 40320, 362880, 3628800, 39916800]


# Définition des permutations pour chaque mouvement
# référencés respectivement par liste_aretes et liste_coins
permutations_aretes = {
    'U': [3, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11],
    'D': [0, 1, 2, 3, 5, 6, 7, 4, 8, 9, 10, 11],
    'F': [0, 9, 2, 3, 4, 8, 6, 7, 1, 5, 10, 11],
    'B': [0, 1, 2, 11, 4, 5, 6, 10, 8, 9, 3, 7],
    'L': [0, 1, 10, 3, 4, 5, 9, 7, 8, 2, 6, 11],
    'R': [8, 1, 2, 3, 11, 5, 6, 7, 4, 9, 10, 0],
}

permutations_coins = {
    'U': [3, 0, 1, 2, 4, 5, 6, 7],
    'D': [0, 1, 2, 3, 5, 6, 7, 4],
    'F': [1, 5, 2, 3, 0, 4, 6, 7],
    'B': [0, 1, 3, 7, 4, 5, 2, 6],
    'L': [0, 2, 6, 3, 4, 1, 5, 7],
    'R': [4, 1, 2, 0, 7, 5, 6, 3],
}

orientations_aretes = {
    'U': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'D': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'F': [0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0],
    'B': [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1],
    'L': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'R': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}

orientations_coins = {
    'U': [0, 0, 0, 0, 0, 0, 0, 0],
    'D': [0, 0, 0, 0, 0, 0, 0, 0],
    'F': [1, 2, 0, 0, 2, 1, 0, 0],
    'B': [0, 0, 1, 2, 0, 0, 2, 1],
    'L': [0, 1, 2, 0, 0, 2, 1, 0],
    'R': [2, 0, 0, 1, 1, 0, 0, 2],
}

# Table qui donne l'axe de rotation en fonction de la rotation effectuée,
# si on fait la rotation en sens anti-horaire il faut multiplier l'axe par -1
axe_rotation = {
    'U': (0, -1, 0),
    'F': (0, 0, -1),
    'R': (-1, 0, 0),
    'D': (0, 1, 0),
    'B': (0, 0, 1),
    'L': (1, 0, 0),
}

# Table des coordonnées pour tracer la surface qui cachera l'intérieur du cube
# pendant la rotation d'une face
hide_coords = {
    'U': [(-3, 1, -3), (3, 1, -3), (3, 1, 3), (-3, 1, 3)],
    'D': [(-3, -1, -3), (3, -1, -3), (3, -1, 3), (-3, -1, 3)],
    'F': [(-3, 3, 1), (-3, -3, 1), (3, -3, 1), (3, 3, 1)],
    'B': [(-3, 3, -1), (-3, -3, -1), (3, -3, -1), (3, 3, -1)],
    'L': [(-1, 3, -3), (-1, -3, -3), (-1, -3, 3), (-1, 3, 3)],
    'R': [(1, 3, -3), (1, -3, -3), (1, -3, 3), (1, 3, 3)],
}

# Liste des points permettant d'ajuster la texture sur la surface
tex_map = [
    (0, 0),
    (0, 1),
    (1, 1),
    (1, 0),
]

# Coordonnées des 8 points permettant de tracer un cube dans l'espace
s = [
    (1, 1, 1),
    (-1, 1, 1),
    (-1, 1, -1),
    (1, 1, -1),
    (1, -1, 1),
    (-1, -1, 1),
    (-1, -1, -1),
    (1, -1, -1),
]

# Fonction qui permet de changer la taille du cube
sommets = lambda x: [list(map(float.__mul__, [x] * 3, point)) for point in s]

indices = [
    (0, 1, 2, 3),
    (4, 5, 6, 7),
    (7, 4, 0, 3),
    (4, 5, 1, 0),
    (5, 6, 2, 1),
    (6, 7, 3, 2),
]

liste_positions = [
    'F', 'L', 'D', 'U', 'R', 'B',
    'DR', 'UB', 'FL', 'BL',
    'DF', 'UR', 'UL', 'DB',
    'DL', 'UF', 'FR', 'BR',
    'UBR', 'UFR', 'UFL', 'DFR',
    'DFL', 'UBL', 'DBL', 'DBR',
]

table_positions_centres = [
    (0, 2, 0), (0, -2, 0), (2, 0, 0),
    (0, 0, 2), (-2, 0, 0), (0, 0, -2),
]

table_positions_aretes = [
    (2, 2, 0), (0, 2, 2), (-2, 2, 0), (0, 2, -2),
    (2, -2, 0), (0, -2, 2), (-2, -2, 0), (0, -2, -2),
    (2, 0, 2), (-2, 0, 2), (-2, 0, -2), (2, 0, -2),
]

table_positions_coins = [
    (2, 2, 2), (-2, 2, 2), (-2, 2, -2), (2, 2, -2),
    (2, -2, 2), (-2, -2, 2), (-2, -2, -2), (2, -2, -2),
]

table_couleurs_centres = [
    [0], [1], [2], [3], [4], [5],
]

table_couleurs_aretes = [
    [0, 2], [0, 3], [0, 4], [0, 5],
    [1, 2], [1, 3], [1, 4], [1, 5],
    [3, 2], [3, 4], [5, 4], [5, 2],
]

table_couleurs_coins = [
    [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2],
    [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5],
]

table_axe_orientation_aretes = [
    (1, 1, 0), (0, 1, 1), (-1, 1, 0), (0, 1, -1),
    (1, -1, 0), (0, -1, 1), (-1, -1, 0), (0, -1, -1),
    (1, 0, 1), (-1, 0, 1), (-1, 0, -1), (1, 0, -1),
]

table_axe_orientation_coins = [
    (1, 1, 1), (-1, 1, 1), (-1, 1, -1), (1, 1, -1),
    (1, -1, 1), (-1, -1, 1), (-1, -1, -1), (1, -1, -1),
]

# Table des facettes qui doivent afficher une couleur pour chaque pièce
table_couleurs = {
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

# Table des (dX, dY, dZ)
# Les paramètres de translation pour positionner les pièces dans
# l'espace par rapport au centre du cube
table_positions = {
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
