from pathlib import Path
from fastapi .responses import FileResponse
from api.config import ASSETS_DIR, LAB_DIR, MACHINE_DIR
from api.models.labs import Lab
import subprocess

def getPeerConfig(ownerID: str,labDir: Path):
    config = Path(f"{labDir}/config/wireguard/peer_{ownerID}/peer_{ownerID}.conf")
    return FileResponse(path=config, filename="peer_config.conf", media_type="application/octet-stream")



def startLab(lab: Lab):
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
        result = subprocess.run(command,capture_output=True, text=True,check=False)
        return getPeerConfig(
            lab.owner_id,labdir
        )
    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
    

