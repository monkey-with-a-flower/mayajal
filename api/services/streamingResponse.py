import asyncio
from pathlib import Path
from fastapi.responses import StreamingResponse

async def streamProcess(command: list[str]):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        yield line.decode()

    return_code = await process.wait()
    yield f"\nProcess exited with code {return_code}\n"