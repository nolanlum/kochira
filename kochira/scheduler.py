import asyncio
from concurrent.futures import Future
import logging

from .service import HookContext


logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, bot):
        self.bot = bot

        self.timeouts = {}
        self.periods = {}

        self._next_period_id = 0

    def _error_handler(self, future):
        exc = future.exception()
        if exc is not None:
            logging.error("Background task error",
                          exc_info=(exc.__class__, exc, exc.__traceback__))

    def schedule_after(self, _time, _task, *_args, **_kwargs):
        """
        Schedule a task to run after a given amount of time.
        """
        logger.info("Scheduling %s.%s in %s", _task.service.name, _task.__name__, _time)

        timeout = None
        ctx = HookContext(_task.service, self.bot)

        async def _handler():
            # ghetto-ass code for removing the timeout on completion
            nonlocal timeout

            await asyncio.sleep(_time.total_seconds())

            r = _task(ctx, *_args, **_kwargs)

            if isinstance(r, Future):
                r.add_done_callback(self._error_handler)

            self.timeouts[_task.service.name].remove(timeout)

        timeout = self.bot.event_loop.create_task(_handler, name=f"timerTask-{_task.service.name}")

        self.timeouts.setdefault(_task.service.name, set()).add(timeout)
        return (_task.service.name, timeout)

    def schedule_every(self, _interval, _task, *_args, **_kwargs):
        """
        Schedule a task to run at every given interval.
        """
        logger.info("Scheduling %s.%s every %s", _task.service.name, _task.__name__, _interval)

        period_id = self._next_period_id
        self._next_period_id += 1

        ctx = HookContext(_task.service, self.bot)

        async def _handler():
            while period_id in self.periods.get(_task.service.name, {}):
                await asyncio.sleep(_interval)

                r = _task(ctx, *_args, **_kwargs)

                if isinstance(r, Future):
                    r.add_done_callback(self._error_handler)

        recurring_task = self.bot.event_loop.create_task(_handler, name=f"recurringTimerTask-{_task.service.name}")
        self.periods.setdefault(_task.service.name, {})[period_id] = recurring_task
        return (_task.service.name, period_id)

    def unschedule_timeout(self, timeout):
        service_name, timeout = timeout
        timeout.cancel()
        self.timeouts[service_name].remove(timeout)

    def unschedule_period(self, period):
        service_name, period_id = period
        del self.periods[service_name][period_id]

    def unschedule_service(self, service):
        logger.info("Unscheduling all tasks for service %s", service.name)

        if service.name in self.timeouts:
            for timeout in list(self.timeouts[service.name]):
                self.unschedule_timeout((service.name, timeout))

            del self.timeouts[service.name]

        if service.name in self.periods:
            del self.periods[service.name]
