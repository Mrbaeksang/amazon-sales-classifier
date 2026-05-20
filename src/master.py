import json
import os
import shutil
import sys
from pathlib import Path


def _bundled_default_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "default_master.json"
    return Path(__file__).parent / "default_master.json"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def master_path() -> Path:
    return app_dir() / "asin_master.json"


def load_master() -> dict:
    p = master_path()
    if not p.exists():
        shutil.copy(_bundled_default_path(), p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_master(data: dict) -> None:
    p = master_path()
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def upsert_asin(data: dict, asin: str, category: str, eye_sub: str | None) -> None:
    data["asins"][asin] = {"category": category, "eye_sub": eye_sub}


def delete_asin(data: dict, asin: str) -> None:
    data["asins"].pop(asin, None)
