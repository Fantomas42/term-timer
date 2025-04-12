# Term Timer

Practice your speed cubing skills on your terminal, for a full 80's vibe.

[![image](https://github.com/fantomas42/term-timer/actions/workflows/kwalitee.yml/badge.svg)](https://github.com/fantomas42/term-timer/actions/workflows/kwalitee.yml)

##  Main Features

- Valid WCA scrambles
- From 2x2x2 to 7x7x7 cubes
- Free-play and recorded solves
- Colorfull cube display
- Handle Bluetooth cubes
- Detailled statistics

## Other Features

- Metronome
- Inspection time
- Easy white cross
- Cube orientation control
- Seed control
- csTimer import
- Cubeast import

## Short demo

![](docs/solve.gif)

## Examples usage

Start timing 3x3x3 solves :

```console
term-timer
```

Start timing showing the scrambled cube :

```console
term-timer -p
```

Start timing 2 solves of 4x4x4 in free-play :

```console
term-timer -c 4 -f 2
```

Start timing with an easy white cross, with 15 secs of inspection :

```console
term-timer -ei 15
```

Show statistics on recorded solves :

```console
term-timer -s
```

Show tendencies graph on recorded solves :

```console
term-timer -g
```

Show last ten recorded solves of 7x7x7 :

```console
term-timer -l 10 -c 7
```

## Installation

``` console
pip install -e .
```

If you want short and efficient scrambles for 3x3x3, please install with
this optional dependency.

``` console
pip install -e .[two-phase]
```

> [!TIP]
> Warning, with this dependency the first launch will intensively compute
> the  resolution tables of the Twophase algorythm.
> It will take several minutes, be patient.

## Acknowledgments

I would like to express my sincere gratitude to the developers of the
following projects, without which Term Timer would not have been possible:

* [Herbert Kociemba's RubiksCube-TwophaseSolver][1] for the highly efficient
  Two-Phase algorithm implementation that enables optimal 3x3x3 cube
  scrambles.

* [trincaog's magiccube][2] for providing an excellent foundation for cube
  modeling and manipulation.

Their outstanding work and contributions to the Rubik's Cube programming
community have been invaluable to this project.

[1]: https://github.com/hkociemba/RubiksCube-TwophaseSolver
[2]: https://github.com/trincaog/magiccube/

## Help

```console
Usage: term-timer [-c CUBE] [-p] [-f] [-i SECONDS] [-b TEMPO] [-e] [-n ITERATIONS] [-r SEED]
                  [-l [SOLVES]] [-s] [-h]
                  [SOLVES]

Speed cubing timer on your terminal.

Positional Arguments:
  SOLVES                Specify the number of solves to be done.
                        Default: Infinite.

Configuration:
  -b, --bluetooth       Use a Bluetooth-connected cube.
                        Default: False.
  -c CUBE, --cube CUBE  Set the size of the cube (from 2 to 7).
                        Default: 3.
  -p, --show-cube       Display the cube in its scrambled state.
                        Default: False.
  -f, --free-play       Enable free play mode to disable recording of solves.
                        Default: False.

Timer:
  -i SECONDS, --countdown SECONDS
                        Set the countdown timer for inspection time in seconds.
                        Default: 0.
  -m TEMPO, --metronome TEMPO
                        Set a metronome beep at a specified tempo in seconds.
                        Default: 0.0.

Scramble:
  -e, --easy-cross      Set the scramble with an easy cross.
                        Default: False.
  -n ITERATIONS, --iterations ITERATIONS
                        Set the number of random moves.
                        Default: Auto.
  -r SEED, --seed SEED  Set a seed for random move generation to ensure repeatable scrambles.
                        Default: None.

Actions:
  -l [SOLVES], --list [SOLVES]
                        Display the last recorded solves.
                        Default: All.
  -g, --graph           Display evolution graph of recorded solves.
                        Default: False.
  -s, --stats           Display statistics of recorded solves.
                        Default: False.
  -h, --help            Display this help message.

Have fun cubing !
```

## Origin Story

While I was diligently working on my personal CFOP databases, which can be
accessed at [https://cubing.fache.fr/](https://cubing.fache.fr/), I
encountered the necessity for a high-quality scrambling tool for a 3x3
Rubik's Cube. This tool was essential for the development of an innovative
type of computer solver for the 3x3 cube.

Once I successfully developed this scrambler, it occurred to me that it
would be a regrettable oversight not to capitalize on this momentum by
creating a timing application based on the scrambler's functionality.

Having produced a straightforward prototype and finding the program to be
quite satisfactory, I further concluded that withholding such a useful tool
from the community would constitute another regrettable oversight.
