import asyncio
from pathlib import Path
from fastapi.responses import FileResponse
from api.config import ASSETS_DIR, LAB_DIR, MACHINE_DIR
from api.models.labs import Lab


def getPeerConfig(labDir: Path):
    config = Path(f"{labDir}/config/wireguard/peer_peer1/peer_peer1.conf")
    return FileResponse(
        path=config,
        filename="peer_config.conf",
        media_type="application/octet-stream"
    )


async def startLab(lab: Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")

    command = ["docker-compose", "-f", f"{ASSETS_DIR}/base_compose.yml"]

    for machine in lab.machines:
        command.extend(["-f", f"{MACHINE_DIR}/{machine.id}.yml"])

    command.extend([
        "--env-file", f"{labdir}/.env",
        "-p", str(lab.id),
        "up",
        "-d"
    ])

    try:
        print(command)

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
        getPeerConfig(labdir)

    except Exception as e:
        yield f"Error: {str(e)}\n"