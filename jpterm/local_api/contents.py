from os import scandir


async def get_content(path: str):
    content = sorted(
        list(scandir(path)), key=lambda entry: (not entry.is_dir(), entry.name)
    )
    return content
