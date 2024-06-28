Once jpterm has been installed, it can be launched from the command line. You can show the help message like so:

```bash
$ jpterm --help

 Usage: jpterm [OPTIONS]

╭─ Options ─────────────────────────────────────────────────────────────────────╮
│ --logo                                    Show the jpterm logo.               │
│ --server                            TEXT  The URL to the Jupyter server.      │
│ --collaborative/--no-collaborative        Collaborative mode (with a server). │
│ --experimental/--no-experimental          Experimental mode (with Jupyverse). │
│ --configfile                        TEXT  Read YAML configuration file.       │
│ --set                               TEXT  Set configuration.                  │
│ --help                                    Show this message and exit.         │
╰───────────────────────────────────────────────────────────────────────────────╯
```

The easiest way to launch jpterm is simply by entering `jpterm` and hitting *Enter*. Jpterm will run locally on your machine, without needing a Jupyter server.

Jpterm can also be a client to a Jupyter server, just like when you use JupyterLab. While JupyterLab is a Web client that runs in the browser, jpterm runs in the terminal. The two main Jupyter servers are [jupyter-server](https://github.com/jupyter-server/jupyter_server) and [jupyverse](https://github.com/jupyter-server/jupyverse). You can install and launch them like so:

```bash
# Install jupyter-server:
pip install "jupyterlab>=4"
pip install jupyter-collaboration
# Launch it:
jupyter lab --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True --no-browser --port=8000

# Or install jupyverse:
pip install "jupyverse[jupyterlab, noauth]"
# Launch it:
jupyverse
```

Then pass the URL of the Jupyter server to jpterm through the `--server` option:

```bash
jpterm --server http://127.0.0.1:8000
```
