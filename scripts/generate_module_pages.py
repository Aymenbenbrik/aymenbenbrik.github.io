"""
Genere une page Quarto par module distinct dans enseignements/modules/.

Chaque page : KPIs + tableau historique + lien GitHub + lien vers la page
detaillee (si existante) + section supports (si dispo).

Auteur : Aymen Ben Brik
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_ENS = ROOT / "data" / "enseignements_detailed.csv"
CSV_SUP = ROOT / "data" / "supports.csv"
OUT_DIR = ROOT / "enseignements" / "modules"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Pages detaillees deja presentes dans enseignements/<slug>.qmd
# Slugs alignes sur ceux du catalogue (enseignements/modules/<slug>.qmd)
DETAILED = {
    "Algèbre 2": "algebre-2",
    "Algèbre 3": "algebre-3",
    "Probabilités": "probabilites",
    "Analyse 4": "analyse-4",
    "Recherche Opérationnelle": "recherche-operationnelle",
    "Machine Learning": "machine-learning",
    "Deep Learning": "deep-learning",
    "Generative Computer Vision": "generative-computer-vision",
    "Programmation Python 2": "python-programming",
    "Programmation Python 3": "python-programming",
    "Outillage Machine Learning": "outillage-machine-learning",
}

DOMAIN_ICON = {
    "Mathématiques et Statistiques": "∫",
    "Intelligence Artificielle": "🤖",
    "Sciences des données": "📊",
    "Encadrement et soutien": "🎯",
}


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def parse_links(s: str) -> list[str]:
    if not s or str(s).lower() == "nan":
        return []
    return [u.strip() for u in str(s).split("|") if u.strip()]


def render_page(module: str, g: pd.DataFrame, sup: pd.DataFrame) -> str:
    domaine = g["domaine"].iloc[0]
    icon = DOMAIN_ICON.get(domaine, "📘")

    annees = sorted(g["annee"].unique())
    niveaux = sorted(g["niveau"].dropna().unique())
    classes = sorted(g["classe"].dropna().unique())
    formations = ", ".join(c for c in classes if c and c != "—")
    heures_total = int(g["charge_horaire"].sum())
    nb_groupes_total = int(g["nb_groupes"].sum())
    nb_annees = len(annees)
    is_coord = bool(g["coordinateur"].any())
    is_anglais = bool(g["anglais"].any())
    is_nouveau = bool(g["nouveau_module"].any())

    liens = []
    for v in g["lien_github"].dropna().unique():
        for u in parse_links(v):
            if u not in liens:
                liens.append(u)

    # YouTube playlist (lien le plus recent, par annee max)
    youtube_url = ""
    if "lien_youtube" in g.columns:
        yt_rows = g[g["lien_youtube"].astype(str).str.startswith("http", na=False)]
        if len(yt_rows):
            # Prendre la playlist de l'annee la plus recente
            yt_rows = yt_rows.sort_values("annee")
            youtube_url = str(yt_rows["lien_youtube"].iloc[-1]).strip()

    # Blackboard / Particularite (optionnels)
    blackboard_url = ""
    if "lien_blackboard" in g.columns:
        bb_rows = g[g["lien_blackboard"].astype(str).str.startswith("http", na=False)]
        if len(bb_rows):
            blackboard_url = str(bb_rows["lien_blackboard"].iloc[-1]).strip()

    detailed_slug = DETAILED.get(module)

    # Tableau historique
    rows_html = []
    for _, r in g.sort_values("annee").iterrows():
        rows_html.append(
            f"| {r['annee']} | {r['niveau']} | {r['classe']} | "
            f"{r['nb_groupes']} | {r['charge_horaire']} h | "
            f"{'✓' if r['coordinateur'] else ''} | "
            f"{'EN' if r['anglais'] else 'FR'} | "
            f"{'NOUVEAU' if r['nouveau_module'] else ''} |"
        )

    # Bloc liens GitHub
    if liens:
        gh_block = "\n".join(
            f"- [{u}]({u})" for u in liens
        )
        gh_section = f"""
## Code & supports sur GitHub

{gh_block}
"""
    else:
        gh_section = ""

    # Bloc YouTube
    if youtube_url:
        youtube_section = f"""
## Playlist YouTube du cours

::: {{.callout-tip appearance="simple"}}
**Toutes les capsules vidéo du cours sont disponibles en ligne :**
[{youtube_url}]({youtube_url})

[![Voir sur YouTube](https://img.shields.io/badge/YouTube-Playlist-red?logo=youtube&logoColor=white&style=for-the-badge)]({youtube_url})
:::
"""
    else:
        youtube_section = ""

    # Bloc Blackboard
    if blackboard_url:
        blackboard_section = f"""
## Ressources Blackboard

- [Espace cours sur Blackboard]({blackboard_url})
"""
    else:
        blackboard_section = ""

    # Bloc page detaillee
    detailed_section = ""
    if detailed_slug:
        detailed_section = f"""
## Page pédagogique détaillée

Pour le programme complet, les objectifs d'apprentissage, le découpage par
chapitre et les ressources annexes, consulter la fiche détaillée :

→ [Voir la fiche pédagogique de {module}](../{detailed_slug}.qmd)
"""

    # Bloc supports : matching tolerant aux suffixes "(ECUEXXX)" dans supports.csv
    def _normalize(s: str) -> str:
        s = re.sub(r"\s*\([^)]*\)\s*", " ", str(s)).strip().lower()
        return re.sub(r"\s+", " ", s)

    target = _normalize(module)
    sup_g = sup[sup["nom_module"].apply(_normalize) == target]
    sup_section = ""
    if len(sup_g):
        sup_lines = ["| Ressource | Statut | Lien |", "|---|---|---|"]
        for _, r in sup_g.iterrows():
            lien = str(r.get("ressource_lien") or "").strip()
            if lien.lower() in ("nan", "none"):
                lien = ""
            statut = str(r.get("ressource_statut") or "").strip()
            if statut.lower() == "nan":
                statut = ""
            link_md = f"[Voir]({lien})" if lien and lien != "#" else "—"
            sup_lines.append(f"| {r['ressource_nom']} | {statut} | {link_md} |")
        sup_section = f"""
## Supports pédagogiques

{chr(10).join(sup_lines)}
"""

    badges = []
    if is_coord:
        badges.append('<span class="badge bg-danger">Coordinateur</span>')
    if is_anglais:
        badges.append('<span class="badge bg-info">Anglais</span>')
    if is_nouveau:
        badges.append('<span class="badge bg-success">Nouveau module</span>')

    badges_html = " ".join(badges)

    page = f"""---
title: "{icon} {module}"
subtitle: "{domaine} · {nb_annees} année(s) · {heures_total} h cumulées"
toc: true
---

{badges_html}

## Synthèse

::: {{.grid}}

::: {{.g-col-6 .g-col-md-3}}
::: {{.card-module}}
**{heures_total} h**<br>
<small>Charge cumulée</small>
:::
:::

::: {{.g-col-6 .g-col-md-3}}
::: {{.card-module}}
**{nb_annees}**<br>
<small>Année(s) dispensée(s)</small>
:::
:::

::: {{.g-col-6 .g-col-md-3}}
::: {{.card-module}}
**{nb_groupes_total}**<br>
<small>Groupes cumulés</small>
:::
:::

::: {{.g-col-6 .g-col-md-3}}
::: {{.card-module}}
**{', '.join(niveaux) or '—'}**<br>
<small>Niveau(x)</small>
:::
:::

:::

**Domaine** : {domaine}
**Formations couvertes** : {formations or '—'}
**Période** : {annees[0]} → {annees[-1]}

## Historique de dispense

| Année | Niveau | Classe | Groupes | Charge | Coord. | Langue | Statut |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows_html)}
{youtube_section}{detailed_section}{gh_section}{blackboard_section}{sup_section}
---

::: {{.callout-note}}
Page générée automatiquement à partir de `data/enseignements_detailed.csv`
(source : `Passage de grade/Enseignement.xlsx`).
:::
"""
    return page


def main():
    df = pd.read_csv(CSV_ENS)
    sup = pd.read_csv(CSV_SUP)

    # Boolean coercion
    for col in ("coordinateur", "anglais", "nouveau_module"):
        df[col] = df[col].astype(str).str.lower().map(
            {"true": True, "false": False}
        ).fillna(False)

    df["lien_github"] = df.get("lien_github", "").astype(str).replace("nan", "")

    n_written = 0
    n_with_link = 0
    index_lines = []
    for module, g in df.groupby("nom_module"):
        slug = slugify(module)
        page = render_page(module, g, sup)
        out = OUT_DIR / f"{slug}.qmd"
        out.write_text(page, encoding="utf-8")
        n_written += 1
        if g["lien_github"].astype(str).str.strip().str.len().max() > 0:
            n_with_link += 1
        index_lines.append((g["domaine"].iloc[0], module, slug,
                            int(g["charge_horaire"].sum()),
                            g["annee"].nunique()))

    # Page index des modules
    idx = OUT_DIR / "index.qmd"
    by_dom: dict[str, list] = {}
    for d, m, s, h, n in index_lines:
        by_dom.setdefault(d, []).append((m, s, h, n))

    n_detailed = sum(1 for m in df['nom_module'].unique() if m in DETAILED)
    parts = [f"""---
title: "Modules — Vue d'ensemble"
subtitle: "Catalogue complet des modules dispensés"
toc: true
---

Catalogue des **{n_written} modules** dispensés à ESB (2016–2026), dont
**{n_detailed} avec fiche pédagogique détaillée** (★).
Cliquez sur un module pour accéder à sa fiche.

::: {{.callout-tip appearance="simple"}}
**Légende** : ★ = fiche pédagogique enrichie (programme détaillé, objectifs
d'apprentissage, ressources). Les autres modules disposent de leur fiche
historique (charge, groupes, années, langue, lien GitHub).
:::

"""]
    for dom in ["Mathématiques et Statistiques", "Intelligence Artificielle",
                "Sciences des données", "Encadrement et soutien"]:
        if dom not in by_dom:
            continue
        icon = DOMAIN_ICON.get(dom, "📘")
        parts.append(f"\n## {icon} {dom}\n")
        parts.append("| Module | Charge cumulée | Années | Fiche |\n|---|---|---|---|")
        for m, s, h, n in sorted(by_dom[dom]):
            star = "★" if m in DETAILED else ""
            parts.append(f"| [{m}]({s}.qmd) | {h} h | {n} | {star} |")
        parts.append("")
    idx.write_text("\n".join(parts), encoding="utf-8")

    print(f"Pages générées : {n_written} dans {OUT_DIR}")
    print(f"  - avec lien GitHub : {n_with_link}")
    print(f"  - avec page détaillée : {sum(1 for m in df['nom_module'].unique() if m in DETAILED)}")
    print(f"Page index : {idx}")


if __name__ == "__main__":
    main()
