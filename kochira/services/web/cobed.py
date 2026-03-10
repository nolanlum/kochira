"""
Remote Cobe service.

Allows the bot to reply whenever its nickname is mentioned using a remote Cobe
brain.
"""

import random
import re

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    url = config.Field(doc="The remote cobed to connect to.")
    username = config.Field(doc="The username to use when connecting.")
    password = config.Field(doc="The password to use when connecting.")
    reply = config.Field(doc="Whether or not to generate replies.", default=True)
    prefix = config.Field(doc="Prefix to trigger brain.", default="?")
    random_replyness = config.Field(doc="Probability the brain will generate a reply for all messages.", default=0.0)


async def reply_and_learn(http, url, username, password, what):
    r = await http.post(url,
                        params={"q": what},
                        headers={"X-Cobed-Auth": username + ":" + password})
    r.raise_for_status()
    return r.text


async def learn(http, url, username, password, what):
    r = await http.post(url,
                        params={"q": what, "n": 1},
                        headers={"X-Cobed-Auth": username + ":" + password})
    r.raise_for_status()


@service.hook("channel_message", priority=-9999)
async def do_reply(ctx, target, origin, message):
    front, _, rest = message.partition(" ")

    mention = False
    reply = False

    if ctx.config.prefix is not None and front.startswith(ctx.config.prefix):
        reply = True
        message = front[len(ctx.config.prefix):] + " " + rest
    elif front.strip(",:").lower() == ctx.client.nickname.lower():
        mention = True
        reply = True
        message = rest
    elif random.random() < ctx.config.random_replyness:
        reply = True

    message = message.strip()

    if re.search(r"\b{}\b".format(re.escape(ctx.client.nickname)), message, re.I) is not None:
        reply = True

    if reply and ctx.config.reply:
        reply_message = await reply_and_learn(ctx.bot.http,
                                              ctx.config.url,
                                              ctx.config.username,
                                              ctx.config.password,
                                              message)

        if mention:
            await ctx.respond(reply_message)
        else:
            await ctx.message(reply_message)
    elif message:
        await learn(ctx.bot.http, ctx.config.url, ctx.config.username, ctx.config.password, message)
