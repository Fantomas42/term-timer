from term_timer.gl.cube import Cube
from term_timer.gl.renderer import render
from term_timer.gl.window import Window


def main(cube):
    window = Window(
        1024, 720,
        fps=144,
    )
    window.add_event_rotations(cube)

    count = 0

    while True:
        window.prepare()
        render(cube)
        window.update()

        if count < 2:
            count += 1
            window.camera.animation(0, 0, 90)

    window.quit()


if __name__ == '__main__':
    main(Cube())
