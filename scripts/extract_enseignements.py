"""
Extrait et nettoie les donnees du fichier Enseignement.xlsx vers
data/enseignements_detailed.csv (schema attendu par enseignements/index.qmd).

Schema cible :
  domaine, annee, nom_module, niveau, classe, nb_groupes, anglais,
  charge_horaire, coordinateur, nouveau_module, ecole

Auteur : Aymen Ben Brik
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd
from pathlib import Path

XLSX = Path(r"C:\Users\aymen\OneDrive\Bureau\Passage de grade\Enseignement.xlsx")
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)


def strip_accents(s: str) -> str:
    if not isinstance(s, str):
        return s
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Domain detection -- based on canonical module names (accent-insensitive)
DOMAIN_RULES = [
    ("Intelligence artificielle", [
        "machine learning", "deep learning", "apprentissage statistique",
        "outillage machine learning", "generative computer vision",
        "intelligence artificielle", "nlp",
    ]),
    ("Probabilites & Statistiques", [
        "probabilite", "statistique", "stats inferentielle", "series temporelles",
        "modeles lineaires generalises", "integration et probabilites",
        "satistiques",  # typo present dans le fichier source
    ]),
    ("Analyse des donnees", [
        "analyse des donnees", "data mining", "analyse statistique avec r",
        "introduction data science",
    ]),
    ("Programmation", [
        "programmation python", "programmation avec r", "atelier de programmation",
    ]),
    ("Mathematiques financieres", [
        "recherche operationnelle", "optimisation numerique",
        "fondements de la theorie de la decision",
    ]),
    ("Mathematiques", [
        "algebre", "analyse 2", "analyse 4", "mathematiques",
        "logique mathematique", "fondamentaux des mathematiques",
        "cours de soutien",  # cours de soutien math (non specifie)
    ]),
]

# Display label for the domains (with accents)
DOMAIN_DISPLAY = {
    "Intelligence artificielle": "Intelligence artificielle",
    "Probabilites & Statistiques": "Probabilités & Statistiques",
    "Analyse des donnees": "Analyse des données",
    "Programmation": "Programmation",
    "Mathematiques financieres": "Mathématiques financières",
    "Mathematiques": "Mathématiques",
}


def detect_domain(module: str) -> str:
    m = strip_accents(str(module).lower().strip())
    for domain, keywords in DOMAIN_RULES:
        for kw in keywords:
            if kw in m:
                return DOMAIN_DISPLAY[domain]
    return "Autres"


def normalize_module_name(m: str) -> str:
    """Clean trailing whitespace / non-breaking chars from module names."""
    if not isinstance(m, str):
        return m
    # Strip whitespace, NBSP, zero-width, trailing dots
    m = m.replace(" ", " ").replace("​", "")
    m = re.sub(r"\s+", " ", m).strip()
    return m


def to_bool(v, true_values=("oui", "yes", "true", "1", "x")) -> bool:
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in true_values or s == "1.0"


def is_english(v) -> bool:
    """The 'Cours en Anglais' column holds the number of hours taught in English."""
    if pd.isna(v):
        return False
    try:
        return float(v) > 0
    except (ValueError, TypeError):
        return str(v).strip().lower() in ("oui", "yes", "true", "x")


def to_int(v, default=1) -> int:
    if pd.isna(v):
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def to_niveau(n) -> str:
    """Normalise L1/L2/L3 -> Licence, M1/M2 -> Master."""
    if pd.isna(n):
        return ""
    s = str(n).strip().upper()
    if s.startswith("L"):
        return "Licence"
    if s.startswith("M"):
        return "Master"
    return s


def main():
    # Header is on row index 3 (4th row)
    df = pd.read_excel(XLSX, sheet_name="Module ", header=3)
    df = df.dropna(how="all").reset_index(drop=True)

    # Strip column names
    df.columns = [str(c).strip() for c in df.columns]

    # Forward-fill the "Annee Universitaire" merged cells
    annee_col = next((c for c in df.columns if "Ann" in c and "Univ" in c), None)
    if annee_col is None:
        raise RuntimeError(f"Annee column not found in: {df.columns.tolist()}")
    df[annee_col] = df[annee_col].ffill()

    # Keep only rows that have a Module name
    df = df[df["Module"].notna()].copy()
    df["Module"] = df["Module"].astype(str).map(normalize_module_name)

    # Find column names by partial match (handle trailing spaces)
    def find_col(*needles):
        for c in df.columns:
            cl = c.lower()
            if all(n.lower() in cl for n in needles):
                return c
        return None

    col_resp = find_col("Responsable", "Module")
    col_form = find_col("Formation")
    col_niv = find_col("Niveau")
    col_charge_module = find_col("Charge horaire par module")
    col_groupes = find_col("Nombre", "groupe")
    col_nouveau = find_col("Nouveau", "Module")
    col_anglais = find_col("Anglais")
    col_domaine_xlsx = find_col("Domaine")
    col_lien = find_col("Lien")

    print(f"  Total module-rows lues : {len(df)}")

    def parse_liens(v):
        """Le champ peut contenir 1 ou plusieurs liens, separes par newline.
        On accepte soit un slug 'Aymenbenbrik/<repo>', soit une URL complete."""
        if pd.isna(v):
            return ""
        out = []
        for part in str(v).replace("\r", "\n").split("\n"):
            part = part.strip()
            if not part:
                continue
            if part.startswith("http"):
                out.append(part)
            elif "/" in part:
                out.append("https://github.com/" + part)
            else:
                out.append(part)
        return " | ".join(out)

    rows = []
    for _, r in df.iterrows():
        module = r["Module"]
        # Skip lines that are not real modules (cours de soutien sometimes empty)
        if not module or module.lower() == "nan":
            continue

        formation = str(r.get(col_form) or "").strip()
        niveau_raw = r.get(col_niv)

        # Domaine : priorité au libellé Excel ; fallback détection auto
        if col_domaine_xlsx:
            d_xlsx = r.get(col_domaine_xlsx)
            if pd.notna(d_xlsx) and str(d_xlsx).strip():
                domaine = str(d_xlsx).strip()
            else:
                domaine = detect_domain(module)
        else:
            domaine = detect_domain(module)

        rows.append({
            "domaine": domaine,
            "annee": str(r[annee_col]).strip(),
            "nom_module": module,
            "niveau": to_niveau(niveau_raw),
            "classe": formation if formation and formation.lower() != "nan" else "—",
            "nb_groupes": to_int(r.get(col_groupes), default=1),
            "anglais": is_english(r.get(col_anglais)),
            "charge_horaire": to_int(r.get(col_charge_module), default=0),
            "coordinateur": to_bool(r.get(col_resp)),
            "nouveau_module": to_bool(r.get(col_nouveau)),
            "ecole": "ESB",
            "lien_github": parse_liens(r.get(col_lien)) if col_lien else "",
        })

    out_df = pd.DataFrame(rows)

    # Drop rows with charge_horaire == 0 (artefacts)
    n_before = len(out_df)
    out_df = out_df[out_df["charge_horaire"] > 0].copy()
    print(f"  Lignes valides (charge > 0) : {len(out_df)} (drop {n_before - len(out_df)})")

    out_path = OUT / "enseignements_detailed.csv"
    out_df.to_csv(out_path, index=False)
    print(f"  -> {out_path} ({len(out_df)} lignes)")

    # Legacy CSV pour les dashboards (schema enseignements.csv)
    semestre_col = next((c for c in df.columns if c.lower().startswith("semestre")), None)
    legacy_rows = []
    for i, r in df.reset_index(drop=True).iterrows():
        module = r["Module"]
        if not module or module.lower() == "nan":
            continue
        formation = str(r.get(col_form) or "").strip()
        legacy_rows.append({
            "module": module,
            "code": "",
            "annee_universitaire": str(r[annee_col]).strip(),
            "semestre": str(r.get(semestre_col) or "").strip() if semestre_col else "",
            "filiere": formation if formation and formation.lower() != "nan" else "",
            "heures": to_int(r.get(col_charge_module), default=0),
            "ects": "",
            "role": "Responsable" if to_bool(r.get(col_resp)) else "Enseignant",
        })
    legacy_df = pd.DataFrame(legacy_rows)
    legacy_df = legacy_df[legacy_df["heures"] > 0].copy()
    legacy_path = OUT / "enseignements.csv"
    legacy_df.to_csv(legacy_path, index=False)
    print(f"  -> {legacy_path} ({len(legacy_df)} lignes -- legacy schema)")

    # Stats
    print("\n=== Repartition par domaine ===")
    print(out_df["domaine"].value_counts().to_string())
    print("\n=== Repartition par annee ===")
    print(out_df["annee"].value_counts().sort_index().to_string())
    print("\n=== Repartition par niveau ===")
    print(out_df["niveau"].value_counts().to_string())
    print(f"\n=== Modules distincts : {out_df['nom_module'].nunique()} ===")
    print(f"=== Charge totale cumulée : {out_df['charge_horaire'].sum()} h ===")
    print(f"=== Coordinateur : {out_df['coordinateur'].sum()} lignes ===")
    print(f"=== Nouveaux modules : {out_df['nouveau_module'].sum()} lignes ===")
    print(f"=== Anglais : {out_df['anglais'].sum()} lignes ===")


if __name__ == "__main__":
    main()
