import atexit
import subprocess
from time import sleep
from typing import Optional

import typer

from .app import JptermApp

SERVER_PROCESS = None
BASE_URL = None


def stop_server():
    if SERVER_PROCESS:
        SERVER_PROCESS.terminate()


atexit.register(stop_server)


def main(
    launch_server: bool = typer.Option(False, help="Launch a Jupyter server."),
    server_host: str = typer.Option("127.0.0.1", help="The Jupyter server's host IP address."),
    server_port: int = typer.Option(8000, help="The Jupyter server's port number."),
    use_server: Optional[str] = typer.Option(None, help="The URL to the running Jupyter server."),
):
    global SERVER_PROCESS, BASE_URL
    if launch_server:
        SERVER_PROCESS = subprocess.Popen(
            ["jupyverse", "--authenticator.mode=noauth", f"--host={server_host}", f"--port={server_port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for line in SERVER_PROCESS.stderr:
            if b"Uvicorn running" in line:
                break
    if launch_server or use_server:
        if use_server:
            BASE_URL = use_server
        else:
            BASE_URL = f"http://{server_host}:{server_port}"
        import jpterm.remote_api.contents as api_contents
    else:
        import jpterm.local_api.contents as api_contents

    class api:
        contents = api_contents

    JptermApp.api = api
    JptermApp.run(title="JPTerm", log="textual.log")


def cli():
    typer.run(main)


if __name__ == "__main__":
    cli()
