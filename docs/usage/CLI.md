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

Use `show` to display a document inline using the same editor selection as the TUI:

```bash
jpterm show analysis.ipynb
jpterm show script.py
jpterm show notes.txt
jpterm show analysis.ipynb --json
jpterm --server http://127.0.0.1:8000 show analysis.ipynb
jpterm --server http://127.0.0.1:8000 --collaborative show analysis.ipynb
```

The default display uses the file's registered editor in read-only mode. Textual
prepares the full-height layout off-screen, then prints it once below the shell
prompt and returns
automatically, leaving the whole document in terminal scrollback without a vertical scrollbar.
No kernel is started and cells are not executed. `--json` prints the document source without an
inline display and is suitable for pipes and scripts. For notebooks this is the
notebook JSON; for text files it is a JSON string.
Server paths are relative to the server's contents root. Collaborative reads wait
for the initial CRDT synchronization before displaying the notebook. Use
`show --timeout SECONDS` to change the default 30-second loading timeout.

To run the CLI integration tests against a temporary Jupyverse server:

```bash
uv run --group test pytest tests/test_server_cli.py -v
```

The tests start a non-collaborative server on an available local port, serve files
from a temporary directory, and shut the server down afterward.
