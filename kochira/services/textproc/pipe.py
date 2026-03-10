"""
Pipable commands.

Allow the outputs of commands to be piped into each other.
"""

import asyncio
import re
from kochira.client import Client
from kochira.service import Service, HookContext

service = Service(__name__, __doc__)


class BufferedClient(Client):
    class context_factory(HookContext):
        def respond(self, message):
            return self.message(message)

    def __init__(self, client):
        self.__dict__.update(client.__dict__)
        self.buffer = []

    async def message(self, target, message):
        self.buffer.append(message)


# From http://stackoverflow.com/questions/18092354/python-split-string-without-splitting-escaped-character
def split_unescape(s, delim, escape='\\', unescape=True):
    """
    >>> split_unescape('foo,bar', ',')
    ['foo', 'bar']
    >>> split_unescape('foo$,bar', ',', '$')
    ['foo,bar']
    >>> split_unescape('foo$$,bar', ',', '$', unescape=True)
    ['foo$', 'bar']
    >>> split_unescape('foo$$,bar', ',', '$', unescape=False)
    ['foo$$', 'bar']
    >>> split_unescape('foo$', ',', '$', unescape=True)
    ['foo$']
    """
    ret = []
    current = []
    itr = iter(s)
    for ch in itr:
        if ch == escape:
            try:
                # skip the next character; it has been escaped!
                if not unescape:
                    current.append(escape)
                current.append(next(itr))
            except StopIteration:
                if unescape:
                    current.append(escape)
        elif ch == delim:
            # split! (add current to the list and reset it)
            ret.append(''.join(current))
            current = []
        else:
            current.append(ch)
    ret.append(''.join(current))
    return ret


@service.command(r"!pipe (?P<commands>.+)")
async def run_pipe(ctx, commands):
    """
    Run a pipe.

    Pipe commands into each other, e.g.::

        !pipe !quote rand | !benis _ | !topic _
    """

    parts = split_unescape(commands, "|")

    acc = ""

    parts.reverse()

    while parts:
        c = BufferedClient(ctx.client)
        message = parts.pop().strip()

        if "_" in message:
            message = re.sub(r"\b_\b", acc, message)
        else:
            message += " " + acc

        await c._run_hooks("channel_message", ctx.target, ctx.origin,
                           [ctx.target, ctx.origin, message])
        await asyncio.sleep(0)  # allow any non-async hooks to post messages to the buffer
        acc = "\n".join(c.buffer)

    await ctx.respond(acc)
