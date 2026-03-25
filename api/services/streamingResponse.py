import asyncio


async def streamProcess(command:list[str]):
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
    if return_code != 0:
        yield f"\nProcess exited with code {return_code}\n"
