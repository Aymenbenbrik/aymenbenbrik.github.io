"""
Synchronise les URLs Blackboard depuis `Passage de grade/Lien Blackboard.xlsx`
vers la colonne `lien_blackboard` de `data/enseignements_detailed.csv`.

Matching : (nom_module normalisé, classe normalisée).
Multi-URL (col 5 + col 6) joint par "|".

Auteur : Aymen Ben Brik
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "enseignements_detailed.csv"
XLSX = ROOT.parent / "Passage de grade" / "Lien Blackboard.xlsx"


def norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).lower()
    return s


def parse_formations(cell: str) -> list[str]:
    """'MKD/MDSI' -> ['mkd', 'mdsi'] ; 'LFIG' -> ['lfig']."""
    if not cell:
        return []
    return [norm(p) for p in re.split(r"[/,;+&]", str(cell)) if p.strip()]


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb.active

    bb_map: dict[tuple[str, str], list[str]] = {}
    rows_loaded = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        module, formation, niveau, code, url1, url2 = (
            row[0], row[1], row[2], row[3], row[4], row[5]
        )
        if not module:
            continue
        urls = [u for u in (url1, url2) if isinstance(u, str) and u.startswith("http")]
        if not urls:
            continue
        m_key = norm(module)
        for f in parse_formations(formation):
            bb_map[(m_key, f)] = urls
            rows_loaded += 1
    print(f"Lignes Blackboard chargées : {rows_loaded}")

    df = pd.read_csv(CSV)
    df["lien_blackboard"] = df["lien_blackboard"].astype("object").where(
        df["lien_blackboard"].notna(), ""
    )
    n_filled = 0
    n_already = 0
    for idx, r in df.iterrows():
        m_key = norm(r["nom_module"])
        c_key = norm(r["classe"])
        urls = bb_map.get((m_key, c_key))
        if not urls:
            # Tente sans la formation (premier match du module)
            for (mk, _), v in bb_map.items():
                if mk == m_key:
                    urls = v
                    break
        if urls:
            joined = "|".join(urls)
            current = str(r.get("lien_blackboard") or "").strip()
            if current and current != "nan" and current.startswith("http"):
                n_already += 1
            df.at[idx, "lien_blackboard"] = joined
            n_filled += 1
    df.to_csv(CSV, index=False)

    print(f"Lignes CSV remplies : {n_filled} / {len(df)}")
    print(f"  (dont déjà présentes : {n_already})")

    # Audit : modules CSV sans URL Blackboard
    no_bb = df[df["lien_blackboard"].astype(str).str.startswith("http") == False]
    if len(no_bb):
        miss = sorted(no_bb["nom_module"].unique())
        print(f"Sans URL Blackboard ({len(miss)}) :")
        for m in miss:
            classes = sorted(no_bb[no_bb["nom_module"] == m]["classe"].unique())
            print(f"  - {m} | {classes}")


if __name__ == "__main__":
    main()
