# jpterm

`jpterm` is a terminal UI that allows to access documents either locally, or remotely through a Jupyter server.

## Development install

jpterm uses [hatch](https://hatch.pypa.io):

```console
pip install hatch
```

Several development environments are available:

```console
hatch env show
```

To run jpterm with no server, you need the `local_contents` plugin. You can also choose to show notebooks with the `notebook_viewer` or the `notebook_editor` plugin. This will run jpterm with local contents and the notebook viewer:

```console
hatch run dev.local_contents-notebook_viewer:jpterm
```

To run jpterm as a client to a Jupyter server, you need, well, jupyter-server :) You can install it with:

```console
pip install jupyter-server
```

And then launch it (in another terminal):

```console
jupyter server --port=8000 --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True
```

Then launch jpterm with the `remote_contents` plugin, including the configuration file:

```console
hatch run dev.remote_contents-notebook_viewer:jpterm config.yaml
```

If you need to remove the development environments:

```console
hatch env prune
```
