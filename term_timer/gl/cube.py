from term_timer.gl.cube_coord import Cube
from term_timer.gl.renderer import render
from term_timer.gl.window import Window


def main(cube):
    window = Window(
        1024, 720,
        fps=144,
    )
    window.add_event_rotations(cube)

    while True:
        window.prepare()
        render(cube)
        window.update()

    window.quit()


if __name__ == '__main__':
    main(Cube())
