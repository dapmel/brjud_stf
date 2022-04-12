"""Utility functions."""
import lxml.html
import requests
import yaml

with open("utils/config.yml") as ymlfile:
    cfg = yaml.safe_load(ymlfile)


def requester(url: str) -> lxml.html.HtmlElement:
    """Do request and return decoded HTML response."""
    res: requests.models.Response = requests.get(
        url, headers=cfg["requests"]["headers"],
        timeout=cfg["requests"]["timeout"])
    res_decoded: str = res.text.encode("iso-8859-1").decode("utf-8")
    return lxml.html.fromstring(res_decoded)
