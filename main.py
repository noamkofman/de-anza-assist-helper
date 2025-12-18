import csv
import json
import argparse
import requests
from typing import List, Dict, Any, Optional, Tuple

BASE = "https://prod.assistng.org"

UC_RECEIVERS: List[Tuple[str, int]] = [
    ("UCLA", 117),
    ("UC San Diego", 7),
    ("UC Santa Barbara", 128),
    ("UC Irvine", 120),
    ("UC Davis", 89),
    ("UC Riverside", 46),
    ("UC Santa Cruz", 132),
]

HEADERS = {
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (compatible; assist-scraper/1.0)",
}

def http_get_json(url: str, params: Optional[Dict[str, str]] = None) -> Any:
    r = requests.get(url, params=params, headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.json()

def find_institution_id(name_contains: str) -> int:
    data = http_get_json(f"{BASE}/institutions/api")
    target = name_contains.lower().strip()

    for inst in data:
        for n in (inst.get("names") or []):
            nm = (n.get("name") or "").strip()
            if target in nm.lower():
                return int(inst["id"])

    raise RuntimeError(f"Could not find institution containing: {name_contains}")

def list_major_agreements(receiving_id: int, sending_id: int, academic_year_id: int) -> List[Dict[str, Any]]:
    url = f"{BASE}/articulation/api/Agreements/Published/for/{receiving_id}/to/{sending_id}/in/{academic_year_id}"
    data = http_get_json(url, params={"types": "Major"})
    if not data.get("isSuccessful"):
        raise RuntimeError(f"List agreements failed: {data.get('validationFailure')}")
    return data["result"].get("reports", []) or []

def get_agreement_by_key(key: str) -> Dict[str, Any]:
    url = f"{BASE}/articulation/api/Agreements"
    data = http_get_json(url, params={"key": key})
    if not data.get("isSuccessful"):
        raise RuntimeError(f"Get agreement failed: {data.get('validationFailure')}")
    return data["result"]

# ---------- helpers to render course codes ----------

def course_obj_to_code(obj: Dict[str, Any]) -> Optional[str]:
    prefix = (obj.get("prefix") or "").strip()
    num = (obj.get("courseNumber") or "").strip()
    if not prefix or not num:
        return None
    return f"{prefix} {num}"

def sending_course_item_to_code(item: Dict[str, Any]) -> Optional[str]:
    # sending course items store prefix/courseNumber at top level
    prefix = (item.get("prefix") or "").strip()
    num = (item.get("courseNumber") or "").strip()
    if prefix and num:
        return f"{prefix} {num}"
    # sometimes they nest like a "course" object (rare on sending side)
    course = item.get("course") or {}
    return course_obj_to_code(course)

def sending_articulation_to_expr(sending_art: Dict[str, Any]) -> str:
    if not isinstance(sending_art, dict):
        return ""

    if sending_art.get("noArticulationReason"):
        return ""

    items = sending_art.get("items") or []
    if not items:
        return ""

    def is_honors_alternatives(codes: List[str]) -> bool:
        """
        True for patterns like:
          MATH 1A + MATH 1AH
          PHYS 4A + PHYS 4AH
        i.e. same prefix and same number except an optional trailing 'H'.
        """
        if len(codes) < 2:
            return False

        norm = []
        for c in codes:
            parts = c.split()
            if len(parts) != 2:
                return False
            prefix, num = parts[0], parts[1]
            base = num[:-1] if num.endswith("H") else num
            norm.append((prefix, base))

        return len(set(norm)) == 1 and any(c.split()[1].endswith("H") for c in codes)

    group_exprs: List[str] = []

    for it in items:
        if it.get("type") != "CourseGroup":
            continue

        group_items = it.get("items") or []
        codes: List[str] = []
        for gi in group_items:
            if gi.get("type") != "Course":
                continue
            code = sending_course_item_to_code(gi)
            if code:
                codes.append(code)

        if not codes:
            continue

        # Default conj from payload
        conj_raw = (it.get("courseConjunction") or "And").strip().lower()
        conj = "or" if conj_raw == "or" else "and"

        # ✅ KEY FIX: honors alternatives should be OR even if payload says AND
        if is_honors_alternatives(codes):
            conj = "or"

        expr = f" {conj} ".join(codes)
        if len(codes) > 1:
            expr = f"({expr})"

        group_exprs.append(expr)

    if not group_exprs:
        return ""

    if len(group_exprs) == 1:
        return group_exprs[0]

    # Multiple groups: keep simple AND between groups
    return " and ".join(group_exprs)




# ---------- Build map: templateCellId -> De Anza expression ----------

def build_cellid_to_deanza_map(agreement: Dict[str, Any]) -> Dict[str, str]:
    """
    agreement["articulations"] is a JSON string (Template Cell Articulation array).
    Each element has templateCellId and articulation.sendingArticulation.
    """
    raw = agreement.get("articulations")
    if not raw:
        return {}

    try:
        articulations = json.loads(raw)
    except Exception:
        return {}

    out: Dict[str, str] = {}
    for a in articulations:
        cell_id = a.get("templateCellId")
        if not cell_id:
            continue
        articulation = a.get("articulation") or {}
        sending_art = articulation.get("sendingArticulation") or {}
        expr = sending_articulation_to_expr(sending_art)
        if expr:
            out[cell_id] = expr
    return out

# ---------- Walk templateAssets to collect UC-course -> DeAnza mapping ----------

def extract_mappings_from_template_assets(template_assets_json_str: str, cellid_to_deanza: Dict[str, str]) -> List[Dict[str, str]]:
    assets = json.loads(template_assets_json_str)
    assets.sort(key=lambda a: a.get("position", 0))

    current_title = None
    rows_out: List[Dict[str, str]] = []

    for asset in assets:
        t = asset.get("type")

        if t == "RequirementTitle":
            current_title = (asset.get("content") or "").strip() or "Requirements"
            continue

        if t != "RequirementGroup":
            continue

        for sec in (asset.get("sections") or []):
            if sec.get("type") != "Section":
                continue

            for row in (sec.get("rows") or []):
                for cell in (row.get("cells") or []):
                    if cell.get("type") != "Course":
                        continue

                    uc_code = course_obj_to_code(cell.get("course") or {})
                    cell_id = cell.get("id")

                    if not uc_code or not cell_id:
                        continue

                    da_expr = cellid_to_deanza.get(cell_id, "")
                    if not da_expr:
                        continue  # skip if no De Anza articulation exists

                    rows_out.append({
                        "requirement_title": current_title or "Requirements",
                        "for_course": uc_code,
                        "deanza_equiv": da_expr,
                    })

    return rows_out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year-id", type=int, required=True, help="ASSIST academicYearId (e.g., 75, 76, ...)")
    ap.add_argument("--out", default="assist_deanza_to_ucs_mappings2.csv")
    ap.add_argument("--limit-schools", type=int, default=None)
    ap.add_argument("--limit-majors", type=int, default=None)
    args = ap.parse_args()

    sending_id = find_institution_id("De Anza College")

    receivers = UC_RECEIVERS
    if args.limit_schools is not None:
        receivers = receivers[: args.limit_schools]

    final_rows: List[Dict[str, str]] = []

    for uc_name, receiving_id in receivers:
        print(f"\n📚 Listing majors for {uc_name} ...")
        reports = list_major_agreements(receiving_id, sending_id, args.year_id)
        majors = [r for r in reports if r.get("type") == "Major"]
        print(f"✅ Found {len(majors)} majors for {uc_name}")

        if args.limit_majors is not None:
            majors = majors[: args.limit_majors]

        for rep in majors:
            major_label = (rep.get("label") or "").strip() or "Unknown Major"
            key = rep.get("key")
            if not key:
                continue

            print(f"  🌐 Fetching agreement: {major_label}")
            agr = get_agreement_by_key(key)
            major_name = (agr.get("name") or major_label).strip()

            template_assets = agr.get("templateAssets")
            if not template_assets:
                continue

            # ✅ THIS is the missing piece: De Anza equivalents come from agr["articulations"]
            cellid_to_deanza = build_cellid_to_deanza_map(agr)

            mappings = extract_mappings_from_template_assets(template_assets, cellid_to_deanza)
            for m in mappings:
                final_rows.append({
                    "academicYearId": str(args.year_id),
                    "sendingCollege": "De Anza College",
                    "receivingUniversity": uc_name,
                    "major": major_name,
                    "requirement_title": m["requirement_title"],
                    "for_course": m["for_course"],
                    "deanza_equiv": m["deanza_equiv"],
                })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "academicYearId",
                "sendingCollege",
                "receivingUniversity",
                "major",
                "requirement_title",
                "for_course",
                "deanza_equiv",
            ],
        )
        w.writeheader()
        w.writerows(final_rows)

    print(f"\n✅ Done. Wrote {len(final_rows)} rows to: {args.out}")

if __name__ == "__main__":
    main()
