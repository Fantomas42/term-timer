"""The window of the viewer, named after the cube feeding it."""
from dataclasses import dataclass
from dataclasses import field

from cubing_algs.display.gl.host import GlfwHost

from term_timer.viewer.client import CubeView


@dataclass
class CubeViewHost(GlfwHost):
    """
    The glfw host of cubing-algs, titled by the stream it listens to.

    ``frame()`` is the seam the host documents for a consumer layering
    something on the cube, and the title is the whole of what this one
    layers: the loop, the timing and the frame counter are inherited
    untouched.

    The title is written here rather than by the reader thread on
    purpose: glfw wants its window handled from the thread that opened
    it, so the stream only ever changes what the title says, and the
    window learns it at the next frame.
    """

    view: CubeView = field(kw_only=True)

    def frame(self, delta: float) -> None:
        """
        Draw one frame, the title of the window brought up to date.

        Args:
            delta: Seconds gone by since the last frame.

        """
        self.retitle()

        super().frame(delta)

    def retitle(self) -> None:
        """
        Write what the cube says about itself in the title bar.

        In debug mode the host writes its measurements there several
        times a second, on top of this very title: what is set here is
        the base they are appended to, so the two never fight.
        """
        title = self.view.title

        if title == self.title:
            return

        self.title = title

        if self.window is None:
            return

        import glfw  # noqa: PLC0415

        glfw.set_window_title(self.window, title)
