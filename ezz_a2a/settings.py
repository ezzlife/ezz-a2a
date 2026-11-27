"""Constants shared by the worker, the client and the review workflow."""

LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 9130
EPHEMERAL_PORT = 0  # Asks the operating system for a free port.
# First stdout line of the worker: the port it actually bound.
PORT_ANNOUNCEMENT_PREFIX = "A2A_PORT="
MAX_PROMPT_CHARACTERS = 100_000
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
