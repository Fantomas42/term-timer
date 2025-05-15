from OpenGL.GL import GL_LINES
from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_QUADS
from OpenGL.GL import GL_TEXTURE_2D
from OpenGL.GL import glBegin
from OpenGL.GL import glColor
from OpenGL.GL import glColor3fv
from OpenGL.GL import glDisable
from OpenGL.GL import glEnable
from OpenGL.GL import glEnd
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glRotatef
from OpenGL.GL import glScale
from OpenGL.GL import glTexCoord2iv
from OpenGL.GL import glTranslatef
from OpenGL.GL import glVertex3fv
from OpenGL.GL import glVertex3i

from term_timer.gl.data import BLEU
from term_timer.gl.data import NOIR
from term_timer.gl.data import ROUGE
from term_timer.gl.data import VERT
from term_timer.gl.data import axe_rotation
from term_timer.gl.data import hide_coords
from term_timer.gl.data import indices
from term_timer.gl.data import liste_aretes
from term_timer.gl.data import liste_centres
from term_timer.gl.data import liste_coins
from term_timer.gl.data import liste_couleurs
from term_timer.gl.data import permutations_aretes
from term_timer.gl.data import permutations_coins
from term_timer.gl.data import s
from term_timer.gl.data import sommets
from term_timer.gl.data import table_axe_orientation_aretes
from term_timer.gl.data import table_axe_orientation_coins
from term_timer.gl.data import table_couleurs_aretes
from term_timer.gl.data import table_couleurs_centres
from term_timer.gl.data import table_couleurs_coins
from term_timer.gl.data import table_positions_aretes
from term_timer.gl.data import table_positions_centres
from term_timer.gl.data import table_positions_coins
from term_timer.gl.data import tex_map


def repere(echelle=1):
    """ Affiche le repère orthonormé direct """

    glPushMatrix()
    glDisable(GL_TEXTURE_2D)
    glScale(echelle, echelle, echelle)
    glBegin(GL_LINES)
    # Axe X
    glColor(BLEU)
    glVertex3i(0, 0, 0)
    glVertex3i(1, 0, 0)
    # Axe Y
    glColor(ROUGE)
    glVertex3i(0, 0, 0)
    glVertex3i(0, 1, 0)
    # Axe Z
    glColor(VERT)
    glVertex3i(0, 0, 0)
    glVertex3i(0, 0, 1)
    glEnd()
    glEnable(GL_TEXTURE_2D)
    glPopMatrix()


def r_surface(points, couleur):
    """
    Affiche une surface de la couleur spécifiée
    (avec la texture préchargée dans la fenêtre)
    """
    glEnable(GL_TEXTURE_2D)
    if couleur is not None:
        glColor3fv(couleur)
        glBegin(GL_QUADS)
        for i in range(4):
            glTexCoord2iv(tex_map[i])
            glVertex3fv(points[i])
        glEnd()
    glDisable(GL_TEXTURE_2D)


def r_cube(couleurs, echelle=1):
    """
    Affiche un cube dont les faces ont des couleurs différentes.
    Ordre des couleurs : U, D, R, F, L, B
    """
    if echelle == 1:
        liste_sommets = s
    else:
        liste_sommets = sommets(float(echelle))
    for i in range(6):
        points = [liste_sommets[j] for j in indices[i]]
        r_surface(points, couleurs[i])


def get_orientation_param(piece, position, orientation):
    if len(piece) == 2:
        rot_x, rot_y, rot_z = table_axe_orientation_aretes[position]
        theta = 180 * orientation
    elif len(piece) == 3:
        rot_x, rot_y, rot_z = table_axe_orientation_coins[position]
        theta = -120 * orientation
    else:
        rot_x, rot_y, rot_z, theta = 0, 0, 0, 0
    return rot_x, rot_y, rot_z, theta


def render_piece(piece, position, orientation):
    """
    Affiche les facettes de la pièce et la positionne dans l'espace relativement
    au centre du cube.
    @param piece : Donne la chaîne de charactère correspondant à la position
                   de la pièce dans un cube terminé
    @param position : entier entre 0 et 5 pour un centre, 0 et 7 pour un coin
                      et 0 et 11 pour une arête
    @param orientation : entier dans {0,1,2} pour un coin, {0,1} pour une arête
    """
    # Couleurs setup
    c = [liste_couleurs[liste_centres.index(e)] for e in piece]
    couleurs = [None] * 6
    # On récupère la position/orientation de la pièce par rapport au repère
    rot_x, rot_y, rot_z, theta = get_orientation_param(
        piece, position, orientation,
    )
    # Centre
    if len(piece) == 1:
        d_x, d_y, d_z = table_positions_centres[position]

        for i in table_couleurs_centres[position]:
            couleurs[i] = c.pop(0)
    # Arête
    elif len(piece) == 2:
        d_x, d_y, d_z = table_positions_aretes[position]

        for i in table_couleurs_aretes[position]:
            couleurs[i] = c.pop(0)
    # Coin
    elif len(piece) == 3:
        d_x, d_y, d_z = table_positions_coins[position]

        for i in table_couleurs_coins[position]:
            couleurs[i] = c.pop(0)
    # Autre ???
    else:
        msg = 'Unknown piece'
        raise ValueError(msg)

    # Let's OpenGL it !
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    # On positionne d'abord le repère
    glRotatef(theta, rot_x, rot_y, rot_z)
    glTranslatef(d_x, d_y, d_z)
    # Puis on affiche la pièce
    r_cube(couleurs)
    glPopMatrix()


def get_moving_pieces(cube, face):
    """
    Renvoie les liste des pièces affectées et des pièces non affectées
    par la rotation 'face'.
    """
    moving_pieces, non_moving_pieces = [], []
    corner_p = cube.corner_permutation
    corner_o = cube.corners_orientations
    edge_p = cube.edge_permutation
    edge_o = cube.edges_orientations
    # On compare les permutations de rotation de face avec les identités
    # pour récupérer les coins et arêtes affectées
    # Centres
    for i in range(6):
        if face == liste_centres[i]:
            moving_pieces.append((liste_centres[i], i, 0))
        else:
            non_moving_pieces.append((liste_centres[i], i, 0))
    # Coins
    for i in range(8):
        if permutations_coins[face][i] != i:
            # On récupère les coins qui sont affectés
            moving_pieces.append((liste_coins[corner_p[i]], i, corner_o[i]))
        else:
            # On récupère les coins qui ne sont pas affectés
            non_moving_pieces.append((liste_coins[corner_p[i]], i, corner_o[i]))
    # Arêtes
    for i in range(12):
        if permutations_aretes[face][i] != i:
            # On récupère les arêtes qui sont affectées
            moving_pieces.append((liste_aretes[edge_p[i]], i, edge_o[i]))
        else:
            # On récupère les arêtes qui ne sont pas affectées
            non_moving_pieces.append((liste_aretes[edge_p[i]], i, edge_o[i]))
    return moving_pieces, non_moving_pieces


def get_rotation_param(face, power):
    """ Renvoie le vecteur directeur de la rotation """
    axe = tuple(map(lambda x: -x, axe_rotation[face])) if power == 3 else axe_rotation[face]
    theta_max = 181 if power == 2 else 91
    return axe, theta_max


def render(cube):
    """ Rendu du cube en 3D """
    corner_p = cube.corner_permutation
    corner_o = cube.corners_orientations
    edge_p = cube.edge_permutation
    edge_o = cube.edges_orientations
    # Centres
    for i in range(6):
        render_piece(liste_centres[i], i, 0)
    # Arêtes
    for i in range(12):
        render_piece(liste_aretes[edge_p[i]], i, edge_o[i])
    # Coins
    for i in range(8):
        render_piece(liste_coins[corner_p[i]], i, corner_o[i])


def anim_rotation(window, cube, face, power):
    """ Affiche le cube pendant le mouvement (face, power) """
    moving_pieces, non_moving_pieces = get_moving_pieces(cube, face)
    axe, theta_max = get_rotation_param(face, power)
    # On récupère les coords de la surface à tracer
    # pour cacher l'intérieur du cube
    hiding_points = hide_coords[face]
    speed = 6  # 3
    # Theta est l'angle de rotation variant entre 1 et 90 degrés
    for theta in range(1, theta_max, speed):
        window.prepare()

        glMatrixMode(GL_MODELVIEW)
        # On affiche les pieces affectées en les pivotant
        glPushMatrix()
        glRotatef(theta, axe[0], axe[1], axe[2])
        for i in range(9):
            piece, pos, ori = moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, NOIR)
        glPopMatrix()
        # Puis on affiche les pièces immobiles
        for i in range(17):
            piece, pos, ori = non_moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, NOIR)

        window.update()
