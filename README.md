# jpterm

`jpterm` is a terminal UI that allows to access documents either locally, or remotely through a Jupyter server.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```console
pip install hatch
```

By default, jpterm runs with no server:

```console
hatch run dev:jpterm
```

To run jpterm as a client to a Jupyter server, you need, well, jupyter-server :) You can install it (in another environment):

```console
pip install jupyter-server
```

And then launch it (in another terminal):

```console
jupyter server --port=8000 --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True
```

Then launch jpterm with the `txl_remote_contents` plugin enabled and the `txl_local_contents` plugin disabled:

```console
hatch run dev:jpterm --enable txl_remote_contents --disable txl_local_contents
```

To run jpterm with the notebook viewer instead of the notebook editor, disable the `txl_notebook_editor` plugin:

```console
hatch run dev:jpterm --disable txl_notebook_editor
```

If you need to remove the development environment:

```console
hatch env prune
```
