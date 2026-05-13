# backend/mcp_server.py
from interfaces.mcp_server import *  # noqa: F401,F403


if __name__ == "__main__":
    import asyncio

    from interfaces.mcp_server import main

    asyncio.run(main())
