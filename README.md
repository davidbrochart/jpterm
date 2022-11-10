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

Then launch jpterm and pass it the URL to the Jupyter server:

```console
hatch run dev:jpterm --server http://127.0.0.1:8000
```

To run jpterm with the notebook viewer instead of the notebook editor, disable the `txl_notebook_editor` plugin:

```console
hatch run dev:jpterm --disable txl_notebook_editor
```

If you need to remove the development environment:

```console
hatch env prune
```

<div><p>If you want to support jpterm: <a href="https://www.buymeacoffee.com/davidbrochart"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee" style="vertical-align:middle"></a></p></div>
