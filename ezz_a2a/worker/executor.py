import asyncio
from collections.abc import Awaitable, Callable

from a2a.helpers import get_message_text, new_task_from_user_message
from a2a.helpers import new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from ezz_a2a.claude.runner import ClaudeUnavailable
from ezz_a2a.settings import MAX_PROMPT_CHARACTERS

EMPTY_OR_LARGE = "Context is empty or too large."
WORKER_BUSY = "Worker busy; retry from the coordinator."
CLAUDE_UNAVAILABLE = "Claude unavailable: access, quota or timeout."


class ReviewExecutor(AgentExecutor):
    """Runs one review at a time and reports the outcome as an A2A task."""

    def __init__(self, runner: Callable[[str], Awaitable[str]]):
        self.runner = runner
        self.lock = asyncio.Lock()

    async def execute(self, context, event_queue):
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        prompt = get_message_text(context.message)
        if not prompt.strip() or len(prompt) > MAX_PROMPT_CHARACTERS:
            await self._fail(updater, EMPTY_OR_LARGE)
        elif self.lock.locked():
            await self._fail(updater, WORKER_BUSY)
        else:
            async with self.lock:
                await self._review(updater, prompt)

    async def _review(self, updater, prompt: str) -> None:
        await updater.update_status(TaskState.TASK_STATE_WORKING)
        try:
            answer = await self.runner(prompt)
            await updater.add_artifact(parts=[new_text_part(answer)],
                                       metadata=getattr(answer, "metrics", None))
            await updater.update_status(TaskState.TASK_STATE_COMPLETED)
        except (ClaudeUnavailable, asyncio.TimeoutError):
            await self._fail(updater, CLAUDE_UNAVAILABLE)
        except Exception as error:  # CancelledError is a BaseException and propagates.
            # The SDK would forward str(error) to the client; send only the type.
            await self._fail(updater, f"Internal worker error ({type(error).__name__}).")

    @staticmethod
    async def _fail(updater, text: str) -> None:
        try:
            await updater.update_status(TaskState.TASK_STATE_FAILED,
                                        message=new_text_message(text))
        except Exception:
            raise RuntimeError("Could not record the task failure.") from None

    async def cancel(self, context, event_queue):
        raise NotImplementedError("Remote cancellation is not supported; the local timeout is active.")
