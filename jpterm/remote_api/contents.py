import httpx

from jpterm.jpterm import BASE_URL


class Entry:
    """Provide a scandir API"""

    def __init__(self, entry):
        self.entry = entry

    @property
    def name(self):
        return self.entry["name"]

    @property
    def path(self):
        return self.entry["path"]

    def is_dir(self):
        return self.entry["type"] == "directory"


async def get_content(path: str):
    if path == ".":
        path = ""
    else:
        path = f"/{path}"
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/api/contents{path}", params={"content": 1}
        )
    content = [Entry(entry) for entry in r.json()["content"]]
    content = sorted(content, key=lambda entry: (not entry.is_dir(), entry.name))
    return content
