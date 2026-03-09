import asyncio
import inspect
import logging
from collections import deque

from pydle import Client as _Client
from pydle.features.rfc1459.protocol import MESSAGE_LENGTH_LIMIT

from .service import Service, HookContext

logger = logging.getLogger(__name__)


class Client(_Client):
    RECONNECT_MAX_ATTEMPTS = None
    context_factory = HookContext

    def __init__(self, bot, name, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._reconnect_timeout = None
        self._fd = None

        self.backlogs = {}
        self.bot = bot

        self.name = name
        self.network = name

    @property
    def config(self):
        return self.bot.config.clients[self.name]

    @classmethod
    def from_config(cls, bot, name, config):
        client = cls(bot, name, config.nickname,
            username=config.username,
            realname=config.realname,
            tls_client_cert=config.tls.certificate_file,
            tls_client_cert_key=config.tls.certificate_keyfile,
            tls_client_cert_password=config.tls.certificate_password,
            sasl_identity=config.sasl.identity,
            sasl_username=config.sasl.username,
            sasl_password=config.sasl.password
        )

        bot.event_loop.create_task(client.connect(
            hostname=config.hostname,
            password=config.password,
            source_address=(config.source_address, 0),
            port=config.port,
            tls=config.tls.enabled,
            tls_verify=config.tls.verify,
        ))

        return client

    async def connect(self, **kwargs):
        logger.info("Connecting: %s", self.name)
        try:
            await super().connect(**kwargs)
        except (OSError, IOError) as e:
            self._reset_attributes()
            await self.on_disconnect(False)

    async def on_disconnect(self, expected):
        await super().on_disconnect(expected)
        await self._run_hooks("disconnect", None, None, [expected])

    async def on_ctcp_version(self, by, what, contents):
        await self.ctcp_reply(by, "VERSION", self.bot.config.core.version)

    async def on_connect(self):
        logger.info("Connected to IRC: %s", self.name)
        await super().on_connect()

        for name, channel in self.bot.config.clients[self.name].channels.items():
            await self.join(name, password=channel.password)

        await self._run_hooks("connect", None, None)

    def _autotruncate(self, command, target, message, suffix="..."):
        hostmask = self._format_user_mask(self.nickname)
        chunklen = MESSAGE_LENGTH_LIMIT - len("{hostmask} {command} {target} :".format(
            hostmask=hostmask,
            command=command,
            target=target
        )) - 25

        if len(message) > chunklen:
            message = message.encode("utf-8")[:chunklen - len(suffix)] \
                .decode("utf-8", "ignore") + suffix

        return message

    async def message(self, target, message):
        message = self._autotruncate("PRIVMSG", target, message)

        async def _callback():
            await super(Client, self).message(target, message)
            self._add_to_backlog(target, self.nickname, message)
            await self._run_hooks("own_message", target, self.nickname, [target, message])
        return asyncio.run_coroutine_threadsafe(_callback(), self.bot.event_loop)

    async def notice(self, target, message):
        message = self._autotruncate("NOTICE", target, message)

        async def _callback():
            await super(Client, self).notice(target, message)
            await self._run_hooks("own_notice", target, self.nickname, [target, message])
        return asyncio.run_coroutine_threadsafe(_callback(), self.bot.event_loop)

    async def _run_hooks(self, name, target, origin, args=None, kwargs=None):
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        for hook in self.bot.get_hooks(name):
            ctx = self.context_factory(hook.service, self.bot, self, target, origin)

            if not ctx.config.enabled:
                continue

            try:
                r = hook(ctx, *args, **kwargs)

                if inspect.isawaitable(r):
                    r = await r

                if r is Service.EAT:
                    logging.debug("EAT suppressed further hooks.")
                    return Service.EAT
            except BaseException:
                logger.exception("Hook processing failed")

    def _add_to_backlog(self, target, by, message):
        backlog = self.backlogs.setdefault(target, deque([]))
        backlog.appendleft((by, message))

        while len(backlog) > self.bot.config.core.max_backlog:
            backlog.pop()

    async def on_invite(self, channel, by):
        await self._run_hooks("invite", by, by, [channel, by])

    async def on_join(self, channel, user):
        await self._run_hooks("join", channel, user, [channel, user])

    async def on_kill(self, target, by, reason):
        await self._run_hooks("kill", by, by, [target, by, reason])

    async def on_kick(self, channel, target, by, reason=None):
        await self._run_hooks("kick", channel, by, [channel, target, by, reason])

    async def on_mode_change(self, channel, modes, by):
        await self._run_hooks("mode_change", channel, by, [channel, modes, by])

    async def on_user_mode_change(self, modes):
        await self._run_hooks("user_mode_change", None, self.nickname, [modes])

    async def on_channel_message(self, target, by, message):
        self._add_to_backlog(target, by, message)
        await self._run_hooks("channel_message", target, by, [target, by, message])

    async def on_private_message(self, target, by, message):
        self._add_to_backlog(by, by, message)
        await self._run_hooks("private_message", by, by, [by, message])

    async def on_nick_change(self, old, new):
        await self._run_hooks("nick_change", new, new, [old, new])

    async def on_channel_notice(self, target, by, message):
        await self._run_hooks("channel_notice", target, by, [target, by, message])

    async def on_private_notice(self, target, by, message):
        await self._run_hooks("private_notice", by, by, [by, message])

    async def on_part(self, channel, user, message=None):
        await self._run_hooks("part", channel, user, [channel, user, message])

    async def on_topic_change(self, channel, message, by):
        await self._run_hooks("topic_change", channel, by, [channel, message, by])

    async def on_quit(self, user, message=None):
        await self._run_hooks("quit", user, user, [user, message])

    async def on_ctcp(self, by, target, what, contents):
        await self._run_hooks("ctcp", by, by, [by, what, contents])

    async def on_ctcp_action(self, by, what, contents):
        await self._run_hooks("ctcp_action", by, by, [by, what, contents])
