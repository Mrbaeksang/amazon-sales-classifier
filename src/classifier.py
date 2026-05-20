import csv
from dataclasses import dataclass, field
from pathlib import Path


COL_PARENT_ASIN = 0
COL_CHILD_ASIN = 1
COL_TITLE = 2
COL_REVENUE = 17
COL_REVENUE_B2B = 18
COL_QTY = 19
COL_QTY_B2B = 20

EXPECTED_COL_COUNT = 21


@dataclass
class Row:
    asin: str
    title: str
    revenue: float
    qty: int


@dataclass
class Report:
    rows: list[Row]
    by_category: dict[str, tuple[float, int]]
    by_eye_sub: dict[str, tuple[float, int]]
    total_qty: int
    unmatched: list[Row] = field(default_factory=list)


def _parse_usd(s: str) -> float:
    if not s:
        return 0.0
    cleaned = s.replace("US$", "").replace("$", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_int(s: str) -> int:
    if not s:
        return 0
    try:
        return int(float(s.replace(",", "").strip()))
    except ValueError:
        return 0


def read_csv(path: Path) -> list[Row]:
    rows: list[Row] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for raw in reader:
            if len(raw) < EXPECTED_COL_COUNT:
                continue
            asin = raw[COL_CHILD_ASIN].strip()
            if not asin:
                continue
            rows.append(Row(
                asin=asin,
                title=raw[COL_TITLE],
                revenue=_parse_usd(raw[COL_REVENUE]) + _parse_usd(raw[COL_REVENUE_B2B]),
                qty=_parse_int(raw[COL_QTY]) + _parse_int(raw[COL_QTY_B2B]),
            ))
    return rows


def classify(rows: list[Row], master: dict) -> Report:
    asin_map = master["asins"]
    categories = master["categories"]
    eye_subs = master["eye_subcategories"]

    by_cat = {c: [0.0, 0] for c in categories}
    by_eye = {s: [0.0, 0] for s in eye_subs}
    unmatched: list[Row] = []
    total_qty = 0

    for row in rows:
        total_qty += row.qty
        entry = asin_map.get(row.asin)
        if entry is None:
            unmatched.append(row)
            continue
        cat = entry["category"]
        if cat in by_cat:
            by_cat[cat][0] += row.revenue
            by_cat[cat][1] += row.qty
        eye = entry.get("eye_sub")
        if eye and eye in by_eye:
            by_eye[eye][0] += row.revenue
            by_eye[eye][1] += row.qty

    return Report(
        rows=rows,
        by_category={k: (v[0], v[1]) for k, v in by_cat.items()},
        by_eye_sub={k: (v[0], v[1]) for k, v in by_eye.items()},
        total_qty=total_qty,
        unmatched=unmatched,
    )


def format_output1_tsv(report: Report, categories: list[str]) -> str:
    lines = []
    for c in categories:
        rev, _ = report.by_category.get(c, (0.0, 0))
        lines.append(f"{c}\t{rev:.2f}")
    lines.append(f"전체 판매수량\t{report.total_qty}")
    return "\n".join(lines)


def format_output2_tsv(report: Report, eye_subs: list[str]) -> str:
    lines = []
    for s in eye_subs:
        rev, qty = report.by_eye_sub.get(s, (0.0, 0))
        lines.append(f"{s}\t{rev:.2f}\t{qty}")
    return "\n".join(lines)
