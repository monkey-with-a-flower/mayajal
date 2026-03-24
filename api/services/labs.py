from pathlib import Path

from api.config import ASSETS_DIR, LAB_DIR
from api.db import get_db
from api.models.labs import Lab
import subprocess


def startLab(lab: Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")
    command = ["docker-compose","-f",f"{str(ASSETS_DIR)}/base_compose.yml"]
    
    for machine in lab.machines:
        command.append("-f")
        command.append(f"{machine.id}.yml")
    command.append("--env-file")
    command.append(f"{str(labdir)}/.env")
    command.append("-p")
    command.append(f"{lab.id}")
    command.append("up")
    command.append("-d")
    try:
        print (command)
        result = subprocess.run(command,capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
    

