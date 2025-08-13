# Term Timer

Practice your speed cubing skills on your terminal, for a full 80's vibe.

[![image](https://github.com/fantomas42/term-timer/actions/workflows/kwalitee.yml/badge.svg)](https://github.com/fantomas42/term-timer/actions/workflows/kwalitee.yml)

##  Main Features

- Valid WCA scrambles
- From 2x2x2 to 7x7x7 cubes
- Free-play and recorded solves
- Colorfull cube display
- Handle Bluetooth cubes
- Detailled statistics and reconstructions

## Other Features

- Metronome
- Inspection time
- Easy white cross
- Cube orientation control
- Seed control
- Full offline application
- csTimer and Cubeast import

## Short demo

![](docs/solve.gif)

## Examples usage

Start timing 3x3x3 solves :

```console
term-timer solve
```

Start timing in Bluetooth showing the scrambled cube :

```console
term-timer solve -bp
```

Start timing 2 solves of 4x4x4 in free-play :

```console
term-timer solve -c 4 -f 2
```

Start timing with an easy white cross, with 15 secs of inspection :

```console
term-timer solve -ei 15
```

Show statistics on recorded solves :

```console
term-timer stats
```

Show tendencies graph on recorded solves :

```console
term-timer graph
```

Show last ten recorded solves of 7x7x7 :

```console
term-timer list 10 -c 7
```

## Installation

``` console
pip install -e .
```

## Acknowledgments

I would like to express my sincere gratitude to the developers of the
following projects, without which Term Timer would not have been possible:

* [Herbert Kociemba's RubiksCube-TwophaseSolver][1] for the highly efficient
  Two-Phase algorithm implementation that enables optimal 3x3x3 cube
  scrambles.

* [trincaog's magiccube][2] for providing an excellent foundation for cube
  modeling and manipulation.

* [afedotov's gan-web-bluetooth][3] for his clean and well-structured
  implementation of the GAN Bluetooth cubes.

Their outstanding work and contributions to the Rubik's Cube programming
community have been invaluable to this project.

[1]: https://github.com/hkociemba/RubiksCube-TwophaseSolver
[2]: https://github.com/trincaog/magiccube/
[3]: https://github.com/afedotov/gan-web-bluetooth/

## Demos

![](docs/list.gif)

![](docs/detail.gif)

![](docs/stats.gif)

## Help

### General

```console
Usage: term-timer [-h]
                  {solve,sw,t,list,ls,l,stats,st,s,graph,gr,g,cfop,op,c,detail,dt,d,import,im,i,export,ex,e}
                  ...

Speed cubing timer on your terminal.

Positional Arguments:
  {solve,sw,t,list,ls,l,stats,st,s,graph,gr,g,cfop,op,c,detail,dt,d,import,im,i,export,ex,e}
                        Available commands.
    solve (sw, t)       Start the timer and record solves.
    list (ls, l)        Display recorded solves.
    stats (st, s)       Display statistics.
    graph (gr, g)       Display trend graph.
    cfop (op, c)        Display CFOP cases.
    detail (dt, d)      Display detailed information about solves.
    import (im, i)      Import external solves.
    export (ex, e)      Export solves in HTML.

Options:
  -h, --help            Show this help message and exit.

Have fun cubing !
```

### Timer

```console
Usage: term-timer solve [-h] [-b] [-p] [-c CUBE] [-u SESSION] [-f] [-i SECONDS] [-m TEMPO] [-e]
                        [-n ITERATIONS] [-r SEED]
                        [SOLVES]

Start the speed cubing timer to record and time your solves.

Positional Arguments:
  SOLVES                Specify the number of solves to be done.
                        Default: Infinite.

Options:
  -h, --help            Show this help message and exit.

Configuration:
  -b, --bluetooth       Use a Bluetooth-connected cube.
                        Default: False.
  -p, --show-cube       Display the cube in its scrambled state.
                        Default: False.

Session:
  -c CUBE, --cube CUBE  Set the size of the cube (from 2 to 7).
                        Default: 3.
  -u SESSION, --session SESSION
                        Name of the session for solves.
                        Default: None.
  -f, --free-play       Enable free play mode to disable recording of solves.
                        Default: False.

Timer:
  -i SECONDS, --countdown SECONDS
                        Set the countdown timer for inspection time in seconds.
                        Default: 0.0.
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
