from pathlib import Path

from api.config import LAB_DIR
from api.db import get_db
from api.models.labs import Lab
import subprocess
import json


def startLab(lab: Lab):
    labdir = Path(f"{LAB_DIR}/{lab.id}")
    command = ["docker-compose"]
    for machine in lab.machines:
        command.append(f"-f {machine.id}.yml")
    command.append(f"-e {labdir.absolute}/.env")
    command.append(f"-name {lab.id}")
    result = subprocess.run(command,capture_output=True, text=True)
    return result.stdout.strip()
    

