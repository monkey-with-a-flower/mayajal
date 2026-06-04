from api.services.streamingResponse import streamProcess
from pathlib import Path
from fastapi.responses import FileResponse
from api.config import ASSETS_DIR, LAB_DIR, MACHINE_DIR
from api.models.labs import Lab


def getPeerConfig(lab: Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")
    config = Path(f"{labdir}/config/wireguard/peer_peer1/peer_peer1.conf")
    if not config.is_file():
        raise FileNotFoundError("Peer configuration is not available. Start the lab first.")
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
        async for chunk in streamProcess(command):
            yield chunk
    except Exception as e:
        yield f"Error: {str(e)}\n"
        
async def stop(labId: str):
    command = ["docker-compose", "-p", labId, "down"]
    try:
        async for chunk in streamProcess(command):
            yield chunk
    except Exception as e:
        yield f"Error: {str(e)}\n"
