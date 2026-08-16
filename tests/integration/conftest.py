import sys

from app.runner.transport import StdioMCPTransport


def make_mock_transport() -> StdioMCPTransport:
    """Build (but don't connect) a transport for the mock GitHub server.

    Deliberately not a yield-fixture: anyio's cancel scopes are bound to the
    asyncio Task they were entered in, and pytest-asyncio runs fixture
    teardown in a different Task than setup/the test body. Each test must
    open and close the transport itself, within its own ``async with``, so
    enter and exit happen in the same task.
    """
    return StdioMCPTransport(command=sys.executable, args=["-m", "mock_servers.github_mock"])
