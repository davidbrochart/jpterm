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
jupyter lab --port=8000 --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True --no-browser
```

Then launch jpterm in another terminal and pass it the URL to the Jupyter server:

```console
jpterm --server http://127.0.0.1:8000
```

If JupyterLab and jpterm are launched with `--collaborative`, you can open a document in
JupyterLab, by opening your browser at http://127.0.0.1:8000, modify it, and see the changes live
in jpterm.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```console
pip install hatch
```

To run a command, you need to point `hatch` to the `dev` environment, e.g. `hatch run dev:jpterm`.
