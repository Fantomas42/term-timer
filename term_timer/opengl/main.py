from term_timer.opengl.cube import Cube
from term_timer.opengl.renderer import render
from term_timer.opengl.window import Window


def main(cube):
    window = Window(
        1024, 720,
        fps=144,
    )
    window.set_keyboard_events(cube)

    count = 0

    while True:
        window.prepare()
        render(cube)
        window.update()

        if count < 2:
            count += 1
            cube.animate_rotations(window, 'z', 90)

    window.quit()


if __name__ == '__main__':
    main(Cube())
