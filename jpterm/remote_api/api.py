from urllib import parse

import httpx

from .contents import Contents
from .kernels import Kernels


class API:
    def __init__(self, url: str) -> None:
        parsed_url = parse.urlparse(url)
        base_url = parse.urljoin(url, parsed_url.path).rstrip("/")
        query_params = parse.parse_qs(parsed_url.query)
        cookies = httpx.Cookies()

        self.contents = Contents(base_url, query_params, cookies)
        self.kernels = Kernels(base_url, query_params, cookies)
