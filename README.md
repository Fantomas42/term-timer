# Term Timer

Speed Cubing Timer on your Terminal.

##  Features

- Valid WCA scrambles
- Free-play and recorded solves
- Scrambled cube display
- Statistics
- Easy white cross
- Seed control
- Rich colors

## Short demo

![](docs/demo.mov)

## Usage

Start timing solves :

```console
mad-cuber$ term-timer
```

Start timings 2 solves in free-play :

```console
mad-cuber$ term-timer -f 2
```

Start timings with easy white cross, showing the scramble :

```console
mad-cuber$ term-timer -c -m ec
```

Show statistics on recorded solves

```console
mad-cuber$ term-timer --stats
```

## Help

```console
usage: term-timer [-h] [-c] [-f] [-s SEED] [-i ITERATIONS] [-m MODE] [--stats] [scrambles]

3x3 timer

positional arguments:
  scrambles             Number of scrambles

options:
  -h, --help            show this help message and exit
  -c, --show-cube       Show the cube scrambled
  -f, --free-play       Disable recording of solves
  -s SEED, --seed SEED  Seed of random moves
  -i ITERATIONS, --iterations ITERATIONS
                        Iterations of random moves
  -m MODE, --mode MODE  Mode of the scramble
  --stats               Show the statistics
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
