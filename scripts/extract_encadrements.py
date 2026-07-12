"""
Extrait et nettoie les donnees du fichier encadrement.xlsx vers 3 CSVs prets
pour la page Encadrement des projets.

Genere :
  - data/ai4u_projects.csv         (Maitre de stage / PO / Stage d'ete)
  - data/encadrement_academique.csv (Encadrant + Rapporteur consolides)
  - data/president_jury.csv

Auteur : Aymen Ben Brik
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path

XLSX = Path(r"C:\Users\aymen\OneDrive\Bureau\Passage de grade\encadrement et activités.xlsx")
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)


def load(sheet, header_row=2):
    df = pd.read_excel(XLSX, sheet_name=sheet, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    if "Année" in df.columns:
        df["Année"] = df["Année"].ffill()
    df = df[df["Nom"].notna()].copy() if "Nom" in df.columns else df
    return df


def detect_type_categorie(row):
    """Detecte le type de soutenance et le perimetre (initial/exec/intl/DD/Jems/Vermeg)."""
    perimetre = []
    for col in ["Initiale", "Exécutif", "Internationale", "DD", "Jems", "Vermeg"]:
        v = row.get(col)
        if pd.notna(v) and str(v).strip().lower() in ("x", "oui", "yes", "true", "1"):
            perimetre.append(col)
    return ", ".join(perimetre) if perimetre else "—"


def detect_type_projet(formation):
    """Detecte le domaine/type d'apres la formation."""
    f = str(formation or "").upper()
    if any(k in f for k in ["BA", "DS", "DSI", "MDSI", "MDS", "AI", "DATA"]):
        return "Data Science / IA"
    if any(k in f for k in ["LMAD", "MAD", "GAMMA", "ACT"]):
        return "Math / Actuariat"
    if any(k in f for k in ["MKD", "BUSINESS"]):
        return "Marketing / Business"
    if any(k in f for k in ["LFIG", "FIG", "INFO"]):
        return "Informatique"
    if any(k in f for k in ["LFG"]):
        return "Gestion"
    return "Autre"


def to_status(remarque, mention):
    """Determine le statut en fonction des annotations."""
    r = str(remarque or "").lower().strip()
    m = str(mention or "").lower().strip()
    if "en cours" in r:
        return "En cours"
    if "redouble" in r or "abandon" in r:
        return "Archivé"
    if "co-encadrement" in r:
        return "Soutenu (co-encadrement)"
    if any(x in m for x in ["tres bien", "très bien", "bien", "passable", "assez bien", "excellent"]):
        return "Soutenu"
    return "Soutenu" if (r and r != "nan") or (m and m != "nan") else "Terminé"


# === 1. AI4U Projects (Maitre de stage + Product Owner + Stage d'ete) ===
print("\n[1] AI4U Projects")
ms = load("Maitre de stage")
print(f"  Maitre de stage : {len(ms)} lignes")

# Stage d'ete a une structure differente
se = load("Stage d'été")
# Renommer pour aligner
se = se.rename(columns={"Projet": "Sujet"})
print(f"  Stage d'ete : {len(se)} lignes")

# Consolide AI4U
ai4u_rows = []
for _, r in ms.iterrows():
    role_str = str(r.get("Rôle") or "").strip()
    if "Product Owner" in role_str and "Maitre" in role_str:
        role = "Maître de stage / Product Owner"
    elif "Product Owner" in role_str:
        role = "Product Owner"
    elif "Maitre" in role_str or "Maître" in role_str:
        role = "Maître de stage"
    elif "Co-encadr" in role_str:
        role = "Co-encadrant"
    else:
        role = role_str or "Maître de stage"
    annee_str = str(r["Année"]).strip()
    statut = "En cours" if annee_str.startswith("2025") else "Terminé"
    ai4u_rows.append({
        "annee": r["Année"],
        "nom": r["Nom"],
        "prenom": r.get("Prénom", ""),
        "niveau": r.get("Niveau", ""),
        "formation": r.get("Formation", ""),
        "role": role,
        "domaine": detect_type_projet(r.get("Formation", "")),
        "cooperation": str(r.get("Cooperation") or "Non"),
        "type": "AI4U",
        "statut": statut,
        "sujet": "",
    })
for _, r in se.iterrows():
    ai4u_rows.append({
        "annee": r["Année"],
        "nom": r["Nom"],
        "prenom": r.get("Prénom", ""),
        "niveau": "",
        "formation": "",
        "role": "Stage d'été",
        "domaine": "Data Science / IA",
        "cooperation": "Non",
        "type": "Stage d'été",
        "statut": "Terminé",
        "sujet": str(r.get("Sujet") or ""),
    })
ai4u_df = pd.DataFrame(ai4u_rows)
ai4u_df.to_csv(OUT / "ai4u_projects.csv", index=False)
print(f"  -> {OUT / 'ai4u_projects.csv'} ({len(ai4u_df)} lignes)")

# === 2. Encadrement academique (Encadrant + Rapporteur) ===
print("\n[2] Encadrement academique")
enc = load("Encadrant Académique")
print(f"  Encadrant : {len(enc)} lignes")
rap = load("Rapporteur")
print(f"  Rapporteur : {len(rap)} lignes")

acad_rows = []
for _, r in enc.iterrows():
    acad_rows.append({
        "annee": r["Année"],
        "nom": r["Nom"],
        "prenom": r.get("Prénom", ""),
        "niveau": r.get("Niveau", ""),
        "formation": r.get("Formation", ""),
        "perimetre": detect_type_categorie(r),
        "role": "Encadrant",
        "domaine": detect_type_projet(r.get("Formation", "")),
        "remarque": str(r.get("Remarque") or ""),
        "mention": str(r.get("Mention") or ""),
        "statut": to_status(r.get("Remarque"), r.get("Mention")),
    })
for _, r in rap.iterrows():
    annee_str = str(r["Année"]).strip()
    statut = "En cours" if annee_str.startswith("2025") else "Soutenu"
    acad_rows.append({
        "annee": r["Année"],
        "nom": r["Nom"],
        "prenom": r.get("Prénom", ""),
        "niveau": r.get("Niveau", ""),
        "formation": r.get("Formation", ""),
        "perimetre": detect_type_categorie(r),
        "role": "Rapporteur",
        "domaine": detect_type_projet(r.get("Formation", "")),
        "remarque": "",
        "mention": "",
        "statut": statut,
    })
acad_df = pd.DataFrame(acad_rows)
acad_df.to_csv(OUT / "encadrement_academique.csv", index=False)
print(f"  -> {OUT / 'encadrement_academique.csv'} ({len(acad_df)} lignes)")

# === 3. President de jury ===
print("\n[3] President de jury")
pj = load("Président de jury")
print(f"  PJ : {len(pj)} lignes")
pj_rows = []
for _, r in pj.iterrows():
    pj_rows.append({
        "annee": r["Année"],
        "nom": r["Nom"],
        "prenom": r.get("Prénom", ""),
        "niveau": r.get("Niveau", ""),
        "formation": r.get("Formation", ""),
        "perimetre": detect_type_categorie(r),
        "domaine": detect_type_projet(r.get("Formation", "")),
        "type_jury": "Soutenance PFE/Mémoire",
        "ecole": "ESB",
    })
pj_df = pd.DataFrame(pj_rows)
pj_df.to_csv(OUT / "president_jury.csv", index=False)
print(f"  -> {OUT / 'president_jury.csv'} ({len(pj_df)} lignes)")

# === Legacy encadrements.csv pour dashboards/index.qmd et evolution.qmd ===
print("\n[Legacy] encadrements.csv (schema dashboards)")
legacy_rows = []

def _annee_int(a):
    """Extrait l'annee numerique du libelle 2018-2019 -> 2019."""
    s = str(a or "").strip()
    if "-" in s:
        try:
            return int(s.split("-")[1])
        except Exception:
            pass
    try:
        return int(float(s))
    except Exception:
        return ""

# Encadrant (PFE / memoires)
for _, r in enc.iterrows():
    legacy_rows.append({
        "annee": _annee_int(r["Année"]),
        "annee_universitaire": str(r["Année"]).strip(),
        "etudiant": f"{str(r.get('Prénom') or '').strip()} {str(r['Nom']).strip()}".strip(),
        "sujet": "",
        "type": "PFE / Mémoire (Encadrant)" if "Master" in str(r.get("Niveau") or "") else "PFE (Encadrant)",
        "filiere": str(r.get("Formation") or "").strip(),
        "statut": to_status(r.get("Remarque"), r.get("Mention")),
        "co_encadrant": "",
    })

# Rapporteur
for _, r in rap.iterrows():
    annee_str = str(r["Année"]).strip()
    legacy_rows.append({
        "annee": _annee_int(r["Année"]),
        "annee_universitaire": annee_str,
        "etudiant": f"{str(r.get('Prénom') or '').strip()} {str(r['Nom']).strip()}".strip(),
        "sujet": "",
        "type": "Rapporteur",
        "filiere": str(r.get("Formation") or "").strip(),
        "statut": "En cours" if annee_str.startswith("2025") else "Soutenu",
        "co_encadrant": "",
    })

# Maitre de stage / Product Owner AI4U
for _, r in ms.iterrows():
    role_str = str(r.get("Rôle") or "").strip()
    annee_str = str(r["Année"]).strip()
    legacy_rows.append({
        "annee": _annee_int(r["Année"]),
        "annee_universitaire": annee_str,
        "etudiant": f"{str(r.get('Prénom') or '').strip()} {str(r['Nom']).strip()}".strip(),
        "sujet": "",
        "type": f"AI4U ({role_str})" if role_str else "AI4U",
        "filiere": str(r.get("Formation") or "").strip(),
        "statut": "En cours" if annee_str.startswith("2025") else "Terminé",
        "co_encadrant": "",
    })

# Stage d'ete
for _, r in se.iterrows():
    legacy_rows.append({
        "annee": _annee_int(r["Année"]),
        "annee_universitaire": str(r["Année"]).strip(),
        "etudiant": f"{str(r.get('Prénom') or '').strip()} {str(r['Nom']).strip()}".strip(),
        "sujet": str(r.get("Sujet") or ""),
        "type": "Stage été",
        "filiere": "—",
        "statut": "Terminé",
        "co_encadrant": "",
    })

# President de jury (en tant que jury, non encadrement)
for _, r in pj.iterrows():
    annee_str = str(r["Année"]).strip()
    legacy_rows.append({
        "annee": _annee_int(r["Année"]),
        "annee_universitaire": annee_str,
        "etudiant": f"{str(r.get('Prénom') or '').strip()} {str(r['Nom']).strip()}".strip(),
        "sujet": "",
        "type": "Président de jury",
        "filiere": str(r.get("Formation") or "").strip(),
        "statut": "En cours" if annee_str.startswith("2025") else "Soutenu",
        "co_encadrant": "",
    })

legacy_df = pd.DataFrame(legacy_rows)
legacy_df.to_csv(OUT / "encadrements.csv", index=False)
print(f"  -> {OUT / 'encadrements.csv'} ({len(legacy_df)} lignes -- legacy schema)")

# === Resume ===
print("\n=== Resume ===")
print(f"  AI4U projects        : {len(ai4u_df):>4d}")
print(f"  Encadrement academique : {len(acad_df):>4d}")
print(f"  President de jury    : {len(pj_df):>4d}")
print(f"  Total                : {len(ai4u_df) + len(acad_df) + len(pj_df):>4d}")

# Stats
print("\n=== Stats AI4U par role ===")
print(ai4u_df["role"].value_counts().to_string())
print("\n=== Stats Acad par role/niveau ===")
print(acad_df.groupby(["role", "niveau"]).size().to_string())
print("\n=== Stats PJ par formation ===")
print(pj_df["formation"].value_counts().head(10).to_string())
