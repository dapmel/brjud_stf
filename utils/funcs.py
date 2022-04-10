"""Utility functions."""
from datetime import datetime
from urllib import request
import lxml.html
import time
import requests
import yaml

with open("utils/config.yml") as ymlfile:
    cfg = yaml.safe_load(ymlfile)


def requester(url: str, format_html: bool = True):
    """Make GET request to the server.

    Can return HTML objects or raw bytes.
    """
    req: request.Request = request.Request(
        url, headers=cfg["requests"]["headers"])
    res: str = request.urlopen(req, timeout=cfg["requests"]["timeout"]).read()
    if format_html:
        # Return an HTML object
        return lxml.html.fromstring(res)
    else:
        # Return raw bytes
        return res


def decoder(string):
    """Decode strings to PT-BR."""
    return string.encode("iso-8859-1").decode("utf-8")


def requester2(url: str) -> lxml.html.HtmlElement:
    """Request and return HTML."""
    res: requests.models.Response = requests.get(
        url, headers=cfg["requests"]["headers"],
        timeout=cfg["requests"]["timeout"])
    res_decoded: str = decoder(res.text)
    return lxml.html.fromstring(res_decoded)


def today():
    """Return today"s date as a formatted string."""
    return datetime.fromtimestamp(time.time()).strftime("%Y%m%d")
