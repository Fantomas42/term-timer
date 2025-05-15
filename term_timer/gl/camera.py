from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glRotatef
from OpenGL.GL import glTranslatef


class Camera:

    def __init__(self):
        self.x, self.y, self.z = 0, 0, 0
        self.rot_x, self.rot_y, self.rot_z = 0, 0, 0

        # Attributs pour l'animation
        self.animation_queue = []
        self.animation_active = False
        self.current_step = 0
        self.animation_steps = 30  # Nombre d'étapes par défaut
        self.animation_x_step = 0
        self.animation_y_step = 0
        self.animation_z_step = 0

    def get_position(self):
        return self.x, self.y, self.z

    def get_rotation(self):
        return self.rot_x, self.rot_y, self.rot_z

    def increase_position(self, dx, dy, dz):
        self.x -= dx
        self.y -= dy
        self.z -= dz

    def increase_rotation(self, d_pitch, d_yaw, d_roll):
        self.rot_x -= d_pitch
        self.rot_y -= d_yaw
        self.rot_z -= d_roll

    def move(self):
        glTranslatef(self.x, self.y, self.z)

    def rotate(self):
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)

    def update(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Traiter l'animation de la caméra si elle est active
        self.process_animation()

        self.move()
        self.rotate()

    def animation(self, x_angle, y_angle, z_angle):
        """Démarre une animation de rotation de la caméra"""
        # Ajouter l'animation à la file d'attente
        self.animation_queue.append((x_angle, y_angle, z_angle))

        # Si aucune animation n'est en cours, démarrer celle-ci
        if not self.animation_active:
            self.start_next_animation()

    def process_animation(self):
        """Traite une étape de l'animation en cours si active"""
        if self.animation_active:
            if self.current_step < self.animation_steps:
                # Appliquer une étape de l'animation
                self.increase_rotation(
                    self.animation_x_step,
                    self.animation_y_step,
                    self.animation_z_step,
                )
                self.current_step += 1
            else:
                # Fin de l'animation actuelle
                self.animation_active = False
                # Démarrer la prochaine animation s'il y en a
                self.start_next_animation()

    def start_next_animation(self):
        """Démarre la prochaine animation dans la file d'attente"""
        # S'il y a des animations en attente, démarrer la prochaine
        if self.animation_queue:
            # Récupérer la prochaine animation
            x_angle, y_angle, z_angle = self.animation_queue.pop(0)

            # Configuration de l'animation
            self.animation_active = True
            self.animation_steps = 30  # Nombre total d'étapes pour l'animation
            self.current_step = 0

            # Angles à atteindre pour chaque étape
            self.animation_x_step = x_angle / self.animation_steps
            self.animation_y_step = y_angle / self.animation_steps
            self.animation_z_step = z_angle / self.animation_steps
