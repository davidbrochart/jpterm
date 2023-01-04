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

To run jpterm without a server:

```bash
jpterm
```

To run jpterm as a client to a Jupyter server, you need, well, jupyter-server :) You can install it through JupyterLab:

```bash
pip install --pre jupyterlab
```

Then launch it with:

```bash
jupyter lab --port=8000 --no-browser

# it will print a URL like: http://127.0.0.1:8000/lab?token=972cbd440db4b35581b25f90c0a88e3a1095534e18251ca8
# you will need the token when launching jpterm, but if you don't want to bother with authentication:
# jupyter lab --port=8000 --no-browser --ServerApp.token='' --ServerApp.password=''
```

Then launch jpterm in another terminal:

```bash
jpterm --server http://127.0.0.1:8000/?token=972cbd440db4b35581b25f90c0a88e3a1095534e18251ca8

# if you launched JupyterLab without authentication:
# jpterm --server http://127.0.0.1:8000
```

If JupyterLab and jpterm are launched with `--collaborative`, you can open a document in
JupyterLab (go to http://127.0.0.1:8000 in your browser), modify it, and see the changes live
in jpterm.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```bash
pip install hatch
```

To run a command, you need to point `hatch` to the `dev` environment, e.g. `hatch run dev:jpterm`.
