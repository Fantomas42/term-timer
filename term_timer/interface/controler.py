import asyncio
from collections.abc import Iterable


class Controler:
    """
    Mixin providing async task control utilities.
    """

    async def wait_control(
            self, tasks: Iterable[asyncio.Task[object]],
    ) -> set[asyncio.Task[object]]:
        """
        Wait for first task to complete, then cancel remaining tasks.
        """
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

        return done
