import asyncio
import atexit
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Union, cast

import typer
import jpterm.remote_api
import jpterm.local_api

SERVER_PROCESS = None


def query_params():
    """Return the query parameters the first time it is called.
    Then return no parameter (very token specific!).
    """
    global QUERY_PARAMS
    res = dict(QUERY_PARAMS)
    QUERY_PARAMS = {}
    return res


def stop_server():
    if SERVER_PROCESS:
        SERVER_PROCESS.terminate()


atexit.register(stop_server)


def main(
    path: Optional[str] = typer.Argument(None, help="The path to the file to open."),
    launch_server: bool = typer.Option(False, help="Launch a Jupyter server."),
    server_host: str = typer.Option(
        "127.0.0.1", help="The Jupyter server's host IP address."
    ),
    server_port: int = typer.Option(8000, help="The Jupyter server's port number."),
    use_server: Optional[str] = typer.Option(
        None, help="The URL to the running Jupyter server."
    ),
    run: Optional[bool] = typer.Option(
        None, help="Run the file passed as argument and exit."
    ),
):
    global SERVER_PROCESS
    api: Union[jpterm.remote_api.API, jpterm.local_api.API]
    if launch_server:
        SERVER_PROCESS = subprocess.Popen(
            [
                "jupyverse",
                "--authenticator.mode=noauth",
                f"--host={server_host}",
                f"--port={server_port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for line in cast(List[bytes], SERVER_PROCESS.stderr):
            if b"Uvicorn running" in line:
                break
    if launch_server or use_server:
        if use_server:
            url = use_server
        else:
            url = f"http://{server_host}:{server_port}"
        api = jpterm.remote_api.API(url)
    else:
        api = jpterm.local_api.API()

    if run:
        if path is None:
            typer.echo("You must pass the path to the file to be run.")
            sys.exit()
        p = Path(path)
        if p.suffix == ".ipynb":
            from .notebook import Notebook

            async def run_nb():
                nb = Notebook(api=api, path=p)
                await nb.open()
                await nb.run_all()
                await nb.close()

            asyncio.run(run_nb())
            sys.exit()
        else:
            typer.echo("This type of file is not supported.")
            sys.exit()
    else:
        from .app import JptermApp

        JptermApp.api = api
        JptermApp.run(title="JPTerm", log="textual.log")
        sys.exit()


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
