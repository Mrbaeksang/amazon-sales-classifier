import json
import os
import shutil
import sys
from pathlib import Path


PROTECTED_CATEGORIES = {"기타", "아이세럼패치"}
EYE_PATCH_CATEGORY = "아이세럼패치"


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


def category_in_use(data: dict, cat: str) -> int:
    return sum(1 for v in data["asins"].values() if v.get("category") == cat)


def eye_sub_in_use(data: dict, sub: str) -> int:
    return sum(1 for v in data["asins"].values() if v.get("eye_sub") == sub)


def add_category(data: dict, name: str) -> None:
    if name in data["categories"]:
        raise ValueError(f"이미 존재하는 카테고리입니다: {name}")
    data["categories"].insert(len(data["categories"]) - 1 if "기타" in data["categories"] else len(data["categories"]), name)


def add_eye_sub(data: dict, name: str) -> None:
    if name in data["eye_subcategories"]:
        raise ValueError(f"이미 존재하는 세부분류입니다: {name}")
    data["eye_subcategories"].append(name)


def rename_category(data: dict, old: str, new: str) -> None:
    if old in PROTECTED_CATEGORIES:
        raise ValueError(f"보호된 카테고리는 이름을 변경할 수 없습니다: {old}")
    if new in data["categories"]:
        raise ValueError(f"이미 존재하는 카테고리입니다: {new}")
    idx = data["categories"].index(old)
    data["categories"][idx] = new
    for v in data["asins"].values():
        if v.get("category") == old:
            v["category"] = new


def rename_eye_sub(data: dict, old: str, new: str) -> None:
    if new in data["eye_subcategories"]:
        raise ValueError(f"이미 존재하는 세부분류입니다: {new}")
    idx = data["eye_subcategories"].index(old)
    data["eye_subcategories"][idx] = new
    for v in data["asins"].values():
        if v.get("eye_sub") == old:
            v["eye_sub"] = new


def delete_category(data: dict, name: str) -> None:
    if name in PROTECTED_CATEGORIES:
        raise ValueError(f"보호된 카테고리는 삭제할 수 없습니다: {name}")
    used = category_in_use(data, name)
    if used > 0:
        raise ValueError(f"이 카테고리에 {used}개 ASIN이 있습니다. 먼저 다른 카테고리로 옮겨주세요.")
    data["categories"].remove(name)


def delete_eye_sub(data: dict, name: str) -> None:
    used = eye_sub_in_use(data, name)
    if used > 0:
        raise ValueError(f"이 세부분류에 {used}개 ASIN이 있습니다. 먼저 다른 세부분류로 옮겨주세요.")
    data["eye_subcategories"].remove(name)


def reorder_category(data: dict, idx: int, direction: int) -> int | None:
    items = data["categories"]
    new_idx = idx + direction
    if 0 <= new_idx < len(items):
        items[idx], items[new_idx] = items[new_idx], items[idx]
        return new_idx
    return None


def reorder_eye_sub(data: dict, idx: int, direction: int) -> int | None:
    items = data["eye_subcategories"]
    new_idx = idx + direction
    if 0 <= new_idx < len(items):
        items[idx], items[new_idx] = items[new_idx], items[idx]
        return new_idx
    return None
