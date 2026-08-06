import shutil
from pathlib import Path

from fastapi import HTTPException, status

from api_test.config import LAB_RUNTIME_DIR, MAYAJAL_MIN_AVAILABLE_MEMORY_MB, MAYAJAL_MIN_FREE_DISK_GB


def host_capacity() -> dict:
    disk = shutil.disk_usage(LAB_RUNTIME_DIR)
    available_memory_mb = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        values = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in meminfo.read_text().splitlines() if ":" in line}
        if "MemAvailable" in values:
            available_memory_mb = int(values["MemAvailable"].split()[0]) // 1024
    return {
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "available_memory_mb": available_memory_mb,
        "safe": disk.free >= MAYAJAL_MIN_FREE_DISK_GB * (1024 ** 3) and (available_memory_mb is None or available_memory_mb >= MAYAJAL_MIN_AVAILABLE_MEMORY_MB),
    }


def require_host_capacity() -> dict:
    capacity = host_capacity()
    if not capacity["safe"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The lab host does not have enough free disk or memory to start another environment.")
    return capacity
