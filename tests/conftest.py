import socket
import subprocess
import time

import pytest
import httpx


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


def ping(url: str) -> bool:
    with httpx.Client() as client:
        try:
            client.get(url)
        except httpx.ConnectError:
            return False
    return True


@pytest.fixture()
def start_jupyverse(capfd):
    server_ready = False
    while not server_ready:
        port = get_open_port()
        command_list = [
            "jupyverse",
            "--no-open-browser",
            f"--uvicorn.port={port}",
        ]
        p = subprocess.Popen(command_list)
        t0 = time.time()
        while True:
            t1 = time.time()
            if t1 - t0 > 10:
                break
            time.sleep(0.5)
            if ping(f"http://127.0.0.1:{port}"):
                out, err = capfd.readouterr()
                if "?token=" in err:
                    i0 = err.find("http://")
                    i1 = err[i0:].find("\n")
                    url = err[i0 : i0 + i1]
                    server_ready = True
                    break
        if not server_ready:
            p.kill()

    yield url
    p.kill()
