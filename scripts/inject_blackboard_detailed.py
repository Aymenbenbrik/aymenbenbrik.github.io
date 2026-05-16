"""
Injecte une section "Espace Blackboard" dans les fiches pédagogiques détaillées
(enseignements/*.qmd, écrites à la main).

Auteur : Aymen Ben Brik
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "enseignements"

# Slug -> liste de (label, url)
BB = {
    "algebre-2": [("LMAD L1", "https://esprit.blackboard.com/ultra/courses/_26547_1/outline")],
    "algebre-3": [("LMAD L2", "https://esprit.blackboard.com/ultra/courses/_26548_1/outline")],
    "analyse-4": [("LMAD L2", "https://esprit.blackboard.com/ultra/courses/_26550_1/outline")],
    "deep-learning": [
        ("BA M1", "https://esprit.blackboard.com/ultra/courses/_26555_1/outline"),
        ("BA M2", "https://esprit.blackboard.com/ultra/courses/_3785_1/outline"),
    ],
    "generative-computer-vision": [("BA M1", "https://esprit.blackboard.com/ultra/courses/_26556_1/outline")],
    "machine-learning": [("BA M1", "https://esprit.blackboard.com/ultra/courses/_3030_1/outline")],
    "outillage-machine-learning": [("MDSI M1", "https://esprit.blackboard.com/ultra/courses/_2962_1/outline")],
    "probabilites": [("LMAD L3", "https://esprit.blackboard.com/ultra/courses/_26563_1/outline")],
    "python-programming": [
        ("LMAD L2 — Python 2", "https://esprit.blackboard.com/ultra/courses/_26567_1/outline"),
        ("LMAD L2 — Python 3", "https://esprit.blackboard.com/ultra/courses/_26568_1/outline"),
    ],
    "recherche-operationnelle": [("LFIG L2", "https://esprit.blackboard.com/ultra/courses/_2178_1/outline")],
}

MARK_START = "<!-- BB-LINKS:START -->"
MARK_END = "<!-- BB-LINKS:END -->"


def make_block(items: list[tuple[str, str]]) -> str:
    bullets = "\n".join(f"- **{label}** : [{url}]({url})" for label, url in items)
    return (
        f"{MARK_START}\n"
        f"## Espace Blackboard\n\n"
        f"::: {{.callout-tip appearance=\"simple\"}}\n"
        f"**Espace(s) cours sur Blackboard ESB :**\n\n"
        f"{bullets}\n"
        f":::\n"
        f"{MARK_END}\n"
    )


def main():
    written = 0
    for slug, items in BB.items():
        p = DIR / f"{slug}.qmd"
        if not p.exists():
            print(f"  ! manquant : {p.name}")
            continue
        text = p.read_text(encoding="utf-8")
        block = make_block(items)

        if MARK_START in text:
            # remplace l'ancien bloc
            start = text.index(MARK_START)
            end = text.index(MARK_END) + len(MARK_END) + 1
            new_text = text[:start] + block + text[end:]
        else:
            # insère juste après la 1ère section "## Présentation" (ou après le YAML)
            anchor = "## Présentation"
            if anchor in text:
                head, _, tail = text.partition(anchor)
                # insère après le paragraphe Présentation (avant la section suivante "## ")
                tail_lines = tail.split("\n")
                # trouve l'index de la section suivante
                idx_next = None
                for i, line in enumerate(tail_lines[1:], start=1):
                    if line.startswith("## "):
                        idx_next = i
                        break
                if idx_next is not None:
                    before = "\n".join(tail_lines[:idx_next])
                    after = "\n".join(tail_lines[idx_next:])
                    new_text = head + anchor + before + "\n" + block + "\n" + after
                else:
                    new_text = text + "\n" + block
            else:
                # pas de section "## Présentation" → ajoute après le YAML
                if text.startswith("---"):
                    end_yaml = text.index("---", 3) + 3
                    new_text = text[:end_yaml] + "\n\n" + block + text[end_yaml:]
                else:
                    new_text = block + "\n" + text

        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            written += 1
            print(f"  OK {p.name}")
    print(f"\nPages modifiées : {written} / {len(BB)}")


if __name__ == "__main__":
    main()
