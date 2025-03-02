# Term Timer

Practice your speed cubing skills on your terminal.

##  Main Features

- Valid WCA scrambles
- From 2x2x2 to NxNxN cubes
- Free-play and recorded solves
- Colorfull cube display
- Detailled statistics

## Other Features

- Metronome
- Inspection time
- Easy white cross
- csTimer import
- Seed control

## Short demo

![](docs/demo.gif)

## Example usage

Start timing 3x3x3 solves :

```console
term-timer
```

Start timing showing the scrambled cube :

```console
term-timer -c
```

Start timing 2 solves of 4x4x4 in free-play :

```console
term-timer -p 4 -f 2
```

Start timing with an easy white cross, with 15 secs of inspection :

```console
term-timer -m ec -i 15
```

Show statistics on recorded solves :

```console
term-timer --stats
```

Show last ten recorded solves of 7x7x7 :

```console
term-timer --list 10 -p 7
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

## Help

```console
usage: term-timer [-h] [-c] [-p PUZZLE] [-i COUNTDOWN] [-b METRONOME] [-f] [-s SEED] [-n ITERATIONS]
                  [-m MODE] [--stats] [--list LIST]
                  [scrambles]

3x3 timer

positional arguments:
  scrambles             Number of scrambles

options:
  -h, --help            show this help message and exit
  -c, --show-cube       Show the cube scrambled
  -p PUZZLE, --puzzle PUZZLE
                        Size of the puzzle
  -i COUNTDOWN, --countdown COUNTDOWN
                        Countdown for inspection time
  -b METRONOME, --metronome METRONOME
                        Make a beep with tempo
  -f, --free-play       Disable recording of solves
  -s SEED, --seed SEED  Seed of random moves
  -n ITERATIONS, --iterations ITERATIONS
                        Iterations of random moves
  -m MODE, --mode MODE  Mode of the scramble
  --stats               Show the statistics
  --list LIST           Show the last solves
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
