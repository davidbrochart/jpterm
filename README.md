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

<div><p>If you want to support jpterm: <a href="https://www.buymeacoffee.com/davidbrochart"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee" style="vertical-align:middle"></a></p></div>
