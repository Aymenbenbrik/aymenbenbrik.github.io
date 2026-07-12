# -*- coding: utf-8 -*-
"""Remplace les rustines print-fence locales par le helper central theme.html_out."""
import io
import re

OPEN = 'print("```{=html}")'
CLOSE = 'print("```")'

# fichier -> (ancre d'import existante, remplacement)
IMPORTS = {
    "index.qmd": (
        "#| output: asis\nimport pandas as pd",
        "#| output: asis\nimport pandas as pd\n\nimport sys\nsys.path.insert(0, \"scripts\")\nfrom theme import html_out",
    ),
    "capsules-video.qmd": (
        "#| output: asis\nimport pandas as pd\n\ndf = pd.read_csv(\"data/playlists.csv\")",
        "#| output: asis\nimport pandas as pd\n\nimport sys\nsys.path.insert(0, \"scripts\")\nfrom theme import html_out\n\ndf = pd.read_csv(\"data/playlists.csv\")",
    ),
    "encadrement/index.qmd": ("from theme import ESPRIT", "from theme import ESPRIT, html_out"),
    "encadrement/ai4u.qmd": ("from theme import ESPRIT, base_layout, mpl_barh",
                             "from theme import ESPRIT, base_layout, mpl_barh, html_out"),
    "encadrement/encadrements.qmd": ("from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh",
                                     "from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh, html_out"),
    "encadrement/president-jury.qmd": ("from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh",
                                       "from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh, html_out"),
    "encadrement/rapporteur.qmd": ("from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh",
                                   "from theme import ESPRIT, evolution_bar, evolution_cumul, mpl_barh, html_out"),
    "enseignements/index.qmd": (
        "import pandas as pd\nfrom pathlib import Path\nfrom html import escape",
        "import pandas as pd\nfrom pathlib import Path\nfrom html import escape\n\nimport sys\nsys.path.insert(0, \"../scripts\")\nfrom theme import html_out",
    ),
}

for path, (old_imp, new_imp) in IMPORTS.items():
    with io.open(path, encoding="utf-8") as f:
        s = f.read()
    assert old_imp in s, f"ancre d'import introuvable dans {path}"
    s = s.replace(old_imp, new_imp, 1)

    # traite chaque cellule asis contenant la rustine
    lines = s.split("\n")
    out, i, n = [], 0, 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() == "```{python}":
            j = i + 1
            cell = []
            while j < len(lines) and lines[j].strip() != "```":
                cell.append(lines[j])
                j += 1
            if any(OPEN in l for l in cell):
                cell = [l for l in cell if l.strip() not in (OPEN, CLOSE)]
                cell = [re.sub(r"^(\s*)print\(", r"\1html_out(", l) for l in cell]
                n += 1
            out.extend(cell)
            if j < len(lines):
                out.append(lines[j])
            i = j + 1
        else:
            i += 1

    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(out))
    print(f"{path} : import ajusté, {n} cellule(s) refactorée(s)")
