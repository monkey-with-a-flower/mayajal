import asyncio
from pathlib import Path
from fastapi.responses import FileResponse,StreamingResponse
from api.config import ASSETS_DIR, LAB_DIR, MACHINE_DIR
from api.models.labs import Lab
import subprocess




def getPeerConfig(lab:Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")
    config = Path(f"{labdir}/config/wireguard/peer_peer1/peer_peer1.conf")
    return FileResponse(path=config, filename="peer_config.conf", media_type="application/octet-stream")



async def startLab(lab: Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")

    command = ["docker-compose","-f",f"{str(ASSETS_DIR)}/base_compose.yml"]
    
    for machine in lab.machines:
        command.append("-f")
        command.append(f"{str(MACHINE_DIR)}/{machine.id}.yml")
    command.append("--env-file")
    command.append(f"{str(labdir)}/.env")
    command.append("-p")
    command.append(f"{lab.id}")
    command.append("up")
    command.append("-d")
    try:
        print (command)
        result = await asyncio.create_subprocess_exec(command,stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)
        while True:
            line = await result.stdout.readline()
            if not line:
                break
            yield line.decode()

        await result.wait()


    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
    

