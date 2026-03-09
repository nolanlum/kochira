import asyncio
import logging

from .service import HookContext


logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, bot):
        self.bot = bot

        self.timeouts = {}
        self.periods = {}

        self._next_period_id = 0

    def _run_task(self, task_fn, ctx, *args, **kwargs):
        """Call a task function and schedule any returned coroutine."""
        import inspect
        r = task_fn(ctx, *args, **kwargs)
        if inspect.isawaitable(r):
            fut = asyncio.ensure_future(r)
            fut.add_done_callback(self._error_handler)
        return r

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

        handle = None
        ctx = HookContext(_task.service, self.bot)

        def _handler():
            nonlocal handle
            self._run_task(_task, ctx, *_args, **_kwargs)
            self.timeouts[_task.service.name].discard(handle)

        handle = self.bot.event_loop.call_later(_time, _handler)

        self.timeouts.setdefault(_task.service.name, set()).add(handle)
        return (_task.service.name, handle)

    def schedule_every(self, _interval, _task, *_args, **_kwargs):
        """
        Schedule a task to run at every given interval.
        """
        logger.info("Scheduling %s.%s every %s", _task.service.name, _task.__name__, _interval)

        period_id = self._next_period_id
        self._next_period_id += 1

        ctx = HookContext(_task.service, self.bot)

        def _handler():
            if period_id not in self.periods.get(_task.service.name, set()):
                return
            self._run_task(_task, ctx, *_args, **_kwargs)
            # Re-arm for next interval.
            self.bot.event_loop.call_later(_interval, _handler)

        self.bot.event_loop.call_later(_interval, _handler)
        self.periods.setdefault(_task.service.name, set()).add(period_id)
        return (_task.service.name, period_id)

    def unschedule_timeout(self, timeout):
        service_name, handle = timeout
        handle.cancel()
        self.timeouts[service_name].discard(handle)

    def unschedule_period(self, period):
        service_name, period_id = period
        self.periods[service_name].discard(period_id)

    def unschedule_service(self, service):
        logger.info("Unscheduling all tasks for service %s", service.name)

        if service.name in self.timeouts:
            for handle in list(self.timeouts[service.name]):
                handle.cancel()
            del self.timeouts[service.name]

        if service.name in self.periods:
            del self.periods[service.name]
