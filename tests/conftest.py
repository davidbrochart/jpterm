import socket
import subprocess
import time

import pytest


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture()
def start_jupyverse(capfd):
    port = get_open_port()
    command_list = [
        "jupyverse",
        "--no-open-browser",
        f"--uvicorn.port={port}",
    ]
    p = subprocess.Popen(command_list)
    while True:
        time.sleep(0.5)
        out, err = capfd.readouterr()
        if "?token=" in err:
            i0 = err.find("http://")
            i1 = err[i0:].find("\n")
            url = err[i0:i0 + i1]
            break
    yield url
    p.kill()
