from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db" 
DB_DIR.mkdir(parents=True, exist_ok=True)
LAB_DIR = BASE_DIR / "labs"
LAB_DIR.mkdir(parents=True, exist_ok=True)
MACHINE_DIR = BASE_DIR / "machines"
MACHINE_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "mayajal.db"

