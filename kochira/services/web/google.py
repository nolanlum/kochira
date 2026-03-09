"""
Google web search.

Run queries on Google and return results.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")
    cx = config.Field(doc="Custom search engine ID.")


@service.command(r"!g (?P<term>.+?)$")
@service.command(r"(?:search for|google) (?P<term>.+?)\??$", mention=True)
@background
def search(ctx, term):
    """
    Google.

    Search for the given terms on Google.
    """

    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": ctx.config.api_key,
            "cx": ctx.config.cx,
            "q": term
        }
    ).json()

    results = r.get("items", [])

    if not results:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    total = len(results)

    ctx.respond(ctx._("({num} of {total}) {title}: {url}").format(
        title=results[0]["title"],
        url=results[0]["link"],
        num=1,
        total=total
    ))

@service.command(r"!image (?P<term>.+?)$")
@service.command(r"image(?: for)? (?P<term>.+?)\??$", mention=True)
@background
def image(ctx, term):
    """
    Image search.

    Search for the given terms on Google.
    """

    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": ctx.config.api_key,
            "cx": ctx.config.cx,
            "searchType": "image",
            "q": term
        }
    ).json()

    results = [
        item
        for item in r.get("items", [])
        if item.get("link").startswith("http")
    ]

    if not results:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    total = len(results)

    ctx.respond(ctx._("({num} of {total}) {url}").format(
        url=results[0]["link"],
        num=1,
        total=total
    ))
