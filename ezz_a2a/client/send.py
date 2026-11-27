from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest, Task, TaskState

CLIENT_TIMEOUT_SECONDS = 240


async def send_task(http_client, base_url, prompt):
    """Read the Agent Card at `base_url`, send `prompt` as a message and collect the results."""
    card = await A2ACardResolver(http_client, base_url).get_agent_card()
    client = ClientFactory(ClientConfig(
        streaming=False, httpx_client=http_client,
    )).create(card)
    request = SendMessageRequest(message=new_text_message(prompt, role=Role.ROLE_USER))
    results = []
    try:
        async for event in client.send_message(request):
            if event.HasField("task"):
                results.append(event.task)
            elif event.HasField("message"):
                results.append(event.message)
    finally:
        await client.close()
    return results


def completed_task(results):
    """Return the final task when it finished in the COMPLETED state, else None."""
    if results and isinstance(results[-1], Task):
        task = results[-1]
        if task.status.state == TaskState.TASK_STATE_COMPLETED:
            return task
    return None
