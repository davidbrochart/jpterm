import rich_click as click

from txl.cli import set_main, txl_main


def jpterm_main(kwargs):
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    set_ = list(kwargs["set_"])
    locals = "[txl_local_contents,txl_local_terminals,txl_local_kernels]"
    remotes = "[txl_remote_contents,txl_remote_terminals,txl_remote_kernels]"
    if server:
        set_.append(f"component.disable={locals}")
        set_.append(f"component.enable={remotes}")
        set_.append(f"component.components.contents.url={server}")
        set_.append(f"component.components.terminals.url={server}")
        set_.append(f"component.components.kernels.url={server}")
        set_.append(f"component.components.contents.collaborative={collaborative}")
    else:
        set_.append(f"component.disable={remotes}")
        set_.append(f"component.enable={locals}")
    kwargs["set_"] = set_
    return kwargs


def main():
    set_main(jpterm_main)
    decorators = [
        click.option("--server", default="", help="The URL to the Jupyter server."),
        click.option(
            "--collaborative/--no-collaborative",
            default=False,
            help="Collaborative mode (with a server).",
        ),
    ]
    _main = txl_main
    for decorator in decorators[::-1]:
        _main = decorator(_main)
    command = click.command(_main)
    command()
