# jpterm

`jpterm` is a terminal UI that allows to access documents either locally, or remotely through a Jupyter server.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```console
pip install hatch
```

To run jpterm with no server:

```console
hatch run dev:jpterm
```

To run jpterm as a client to a Jupyter server, you need, well, jupyter-server :) You can launch it with:

```console
hatch run dev:jupyter lab --port=8000 --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True --no-browser --collaborative
```

Then launch jpterm in another terminal and pass it the URL to the Jupyter server:

```console
hatch run dev:jpterm --server http://127.0.0.1:8000 --collaborative
```

If the Jupyter server and jpterm are launched with `--collaborative`, you can open a document in
JupyterLab, by opening your browser at http://127.0.0.1:8000, modify it, and see the changes live
in jpterm.
