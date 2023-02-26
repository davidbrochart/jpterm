[![Build Status](https://github.com/davidbrochart/jpterm/workflows/CI/badge.svg)](https://github.com/davidbrochart/jpterm/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# jpterm

`jpterm` aims to be the equivalent of JupyterLab in the terminal.

It can work either locally, or remotely through a Jupyter server.

**WARNING**: jpterm is a work in progress, and it is not usable yet.

## Installation

```bash
pip install jpterm --no-cache-dir
```

## Usage

```bash
jpterm
```

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```bash
pip install hatch
hatch run dev:jpterm
```
