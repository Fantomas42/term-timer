"""Text rendering utilities for OpenGL windows."""

from typing import TYPE_CHECKING

import pygame
from OpenGL.GL import GL_BLEND
from OpenGL.GL import GL_COLOR_BUFFER_BIT
from OpenGL.GL import GL_DEPTH_BUFFER_BIT
from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_ONE_MINUS_SRC_ALPHA
from OpenGL.GL import GL_PROJECTION
from OpenGL.GL import GL_RGBA
from OpenGL.GL import GL_SRC_ALPHA
from OpenGL.GL import GL_UNSIGNED_BYTE
from OpenGL.GL import glBlendFunc
from OpenGL.GL import glClear
from OpenGL.GL import glDisable
from OpenGL.GL import glDrawPixels
from OpenGL.GL import glEnable
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glRasterPos2f
from OpenGL.GLU import gluOrtho2D

if TYPE_CHECKING:
    from term_timer.opengl.window import Window

# Constants for waiting message display
WAITING_MESSAGE_TEXT = 'Waiting for Bluetooth connection...'
WAITING_MESSAGE_FONT_SIZE = 24
WAITING_MESSAGE_PADDING = 20
WAITING_MESSAGE_Y_OFFSET = 30


def create_text_surface(
    font: pygame.font.Font,
    text: str,
) -> pygame.Surface:
    """
    Create a text surface with white text on transparent background.
    """
    # Render text with antialiasing
    temp_surface = font.render(
        text,
        True,  # noqa: FBT003
        (255, 255, 255),  # White text
    )

    # Create surface with per-pixel alpha for transparency
    text_surface = pygame.Surface(
        (temp_surface.get_width(), temp_surface.get_height()),
        pygame.SRCALPHA,
    )
    text_surface.fill((0, 0, 0, 0))  # Transparent background
    text_surface.blit(temp_surface, (0, 0))

    return text_surface


def render_waiting_message(
    window: 'Window',
    font: pygame.font.Font,
) -> None:
    """
    Render waiting message in bottom-right corner of the window.
    """
    # Clear buffers
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Switch to 2D orthographic projection
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, window.display[0], 0, window.display[1])

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Create text surface
    text_surface = create_text_surface(font, WAITING_MESSAGE_TEXT)
    text_width = text_surface.get_width()

    # Calculate position for bottom-right corner
    x_pos = window.display[0] - text_width - WAITING_MESSAGE_PADDING
    y_pos = WAITING_MESSAGE_Y_OFFSET

    # Convert to OpenGL format and draw with alpha blending
    text_data = pygame.image.tostring(text_surface, 'RGBA', True)  # noqa: FBT003

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glRasterPos2f(x_pos, y_pos)
    glDrawPixels(
        text_surface.get_width(),
        text_surface.get_height(),
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        text_data,
    )

    glDisable(GL_BLEND)

    # Restore matrices
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
