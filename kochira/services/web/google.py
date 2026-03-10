"""
Google web search.

Run queries on Google and return results.
"""

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")
    cx = config.Field(doc="Custom search engine ID.")


@service.command(r"!g (?P<term>.+?)$")
@service.command(r"(?:search for|google) (?P<term>.+?)\??$", mention=True)
async def search(ctx, term):
    """
    Google.

    Search for the given terms on Google.
    """

    r = (await ctx.bot.http.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": ctx.config.api_key,
            "cx": ctx.config.cx,
            "q": term
        }
    )).json()

    results = r.get("items", [])

    if not results:
        await ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    total = len(results)

    await ctx.respond(ctx._("({num} of {total}) {title}: {url}").format(
        title=results[0]["title"],
        url=results[0]["link"],
        num=1,
        total=total
    ))

@service.command(r"!image (?P<term>.+?)$")
@service.command(r"image(?: for)? (?P<term>.+?)\??$", mention=True)
async def image(ctx, term):
    """
    Image search.

    Search for the given terms on Google.
    """

    r = (await ctx.bot.http.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": ctx.config.api_key,
            "cx": ctx.config.cx,
            "searchType": "image",
            "q": term
        }
    )).json()

    results = [
        item
        for item in r.get("items", [])
        if item.get("link").startswith("http")
    ]

    if not results:
        await ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    total = len(results)

    await ctx.respond(ctx._("({num} of {total}) {url}").format(
        url=results[0]["link"],
        num=1,
        total=total
    ))
