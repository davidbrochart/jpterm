[![Build Status](https://github.com/davidbrochart/jpterm/workflows/CI/badge.svg)](https://github.com/davidbrochart/jpterm/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# jpterm

`jpterm` aims to be the equivalent of JupyterLab in the terminal.

It can work either locally, or remotely through a Jupyter server.

## Installation

```console
pip install jpterm
```

To show the help:

```console
jpterm --help
```

To run jpterm with no server:

```console
jpterm
```

To run jpterm as a client to a Jupyter server, you need, well, jupyter-server :) You can install it through JupyterLab:

```console
pip install --pre jupyterlab
```

Then launch it with:

```console
jupyter lab --port=8000 --no-browser

# it will print a URL like: http://127.0.0.1:8000/lab?token=972cbd440db4b35581b25f90c0a88e3a1095534e18251ca8
# you will need the token when launching jpterm, but if you don't want to be bothered with authentication:
# jupyter lab --port=8000 --no-browser --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True
```

Then launch jpterm in another terminal:

```console
jpterm --server http://127.0.0.1:8000/?token=972cbd440db4b35581b25f90c0a88e3a1095534e18251ca8

# if you launched JupyterLab without authentication:
# jpterm --server http://127.0.0.1:8000
```

If JupyterLab and jpterm are launched with `--collaborative`, you can open a document in
JupyterLab (go to http://127.0.0.1:8000 in your browser), modify it, and see the changes live
in jpterm.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```console
pip install hatch
```

To run a command, you need to point `hatch` to the `dev` environment, e.g. `hatch run dev:jpterm`.
