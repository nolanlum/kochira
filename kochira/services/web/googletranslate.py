"""
Translation between languages.

Use Google Translate to perform translations between languages.
"""

import pycountry

from kochira.service import Service

service = Service(__name__, __doc__)

LANGUAGES = {}

for language in pycountry.languages:
    for name in language.name.split(";"):
        try:
            LANGUAGES[name.strip().lower()] = language.alpha2
        except AttributeError:
            continue


async def perform_translation(http, term, sl, tl):
    return (await http.get(
        "http://translate.google.com/translate_a/single",
        params={
            "client": "t",
            "dt": "t",
            "dt": "rm",
            "sl": sl,
            "tl": tl,
            "q": term,
            "ie": "UTF-8",
            "oe": "UTF-8"
        },
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36"}
    )).json()


@service.command(r"(?:transliterate|romanize) (?P<term>.+?)(?: from (?P<from_lang>.+?))?$", mention=True)
async def transliterate(ctx, term, from_lang=None):
    """
    Transliterate.

    Perform transliteration of languages with non-Roman characters, e.g. Russian,
    Japanese, Thai, etc.
    """

    if from_lang is None:
        sl = None
    else:
        try:
            sl = LANGUAGES[from_lang.lower()]
        except KeyError:
            await ctx.respond(ctx._("Sorry, I don't understand \"{lang}\".").format(lang=from_lang))
            return

    r = await perform_translation(ctx.bot.http, term, sl, sl)

    tlit = " ".join(x["src_translit"] for x in r["sentences"])

    if not tlit:
        await ctx.respond(ctx._("There is no transliteration."))
        return

    await ctx.respond(tlit)


@service.command(r"what is (?P<term>.+) in (?P<to_lang>.+)\??$", mention=True)
@service.command(r"(?:translate) (?P<term>.+?)(?: from (?P<from_lang>.+?))?(?: to (?P<to_lang>.+))?$", mention=True)
@service.command(r"!tra(nslate)?(?: (?P<from_lang>.+?)-(?P<to_lang>.+?))? (?P<term>.+)")
async def translate(ctx, term, to_lang=None, from_lang=None):
    """
    Translate.

    Translate a term between two languages. If a language to translate from is
    not specified, the language will be auto-detected. If a language to
    translate to is not specified, the language will default to English.
    """

    if from_lang is None:
        sl = "auto"
    else:
        try:
            if len(from_lang) == 2:
                sl = from_lang
            else:
                sl = LANGUAGES[from_lang.lower()]
        except KeyError:
            await ctx.respond(ctx._("Sorry, I don't understand from language: \"{lang}\".").format(lang=from_lang))
            return

    if to_lang is None:
        tl = "en"
    else:
        try:
            if len(to_lang) == 2:
                tl = to_lang
            else:
                tl = LANGUAGES[to_lang.lower()]
        except KeyError:
            await ctx.respond(ctx._("Sorry, I don't understand to language: \"{lang}\".").format(lang=to_lang))
            return

    r = await perform_translation(ctx.bot.http, term, sl, tl)

    trans = " ".join(x["trans"] for x in r["sentences"])

    src_tlit = " ".join(x["src_translit"] for x in r["sentences"]).strip()
    tlit = " ".join(x["translit"] for x in r["sentences"]).strip()

    if src_tlit:
        trans = "(" + src_tlit + ") " + trans

    if tlit:
        trans += " (" + tlit + ")"

    await ctx.respond(trans)
