"""
UrbanDictionary lookup.

Retrieves definitions of terms from UrbanDictionary.
"""

from kochira.service import Service

service = Service(__name__, __doc__)


@service.command(r"!ud (?P<term>.+?)(?: (?P<num>\d+))?$")
async def define(ctx, term, num: int=None):
    """
    Define.

    Look up the given term on UrbanDictionary.
    """

    r = (await ctx.bot.http.get("https://api.urbandictionary.com/v0/define", params={
        "term": term
    })).json()

    exact_matches = [
        result for result in r["list"]
        if result["word"].lower() == term
    ]

    if not exact_matches:
        ctx.respond(ctx._("I don't know what \"{term}\" means.").format(term=term))
        return

    if num is None:
        num = 1

    # offset definition
    num -= 1
    total = len(exact_matches)

    if num >= total or num < 0:
        ctx.respond(ctx._("Can't find that definition of \"{term}\".").format(term=term))
        return

    ctx.respond(ctx._("{term}: {definition} ({num} of {total})").format(
        term=term,
        definition=exact_matches[num]["definition"].replace("\r", "").replace("\n", " ").replace("[", "").replace("]",""),
        num=num + 1,
        total=total
    ))
