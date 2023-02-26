import in_n_out as ino
import pkg_resources
from textual.app import App

for ep in pkg_resources.iter_entry_points(group="txl"):
    ep.load()


@ino.inject
def main(app: App):
    app.run()
