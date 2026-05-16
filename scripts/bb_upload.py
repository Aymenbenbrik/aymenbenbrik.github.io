"""
bb_upload.py — Upload récursif d'un repo de module dans son cours Blackboard Ultra.

Workflow :
    1. python bb_upload.py login                            # 1ère fois (interactif)
    2. python bb_upload.py status                           # liste modules + état
    3. python bb_upload.py next                             # prend le prochain pending
    4. python bb_upload.py upload "Algèbre 2" <repo_path>   # cible explicite
    5. python bb_upload.py reset "Algèbre 2"                # repasse à pending

Pré-requis :
    pip install playwright openpyxl
    playwright install chromium

Mapping module → cours : Lien Blackboard.xlsx (colonnes Module/Formation/Niveau/Code/Lien).
État persistant : ~/.bb_upload_state.json
Session navigateur : ~/.bb_session.json

Auteur : Aymen Ben Brik
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

import openpyxl

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

XLSX_PATH = Path(r"C:\Users\aymen\OneDrive\Bureau\Passage de grade\Lien Blackboard.xlsx")
STATE_PATH = Path.home() / ".bb_upload_state.json"
SESSION_PATH = Path.home() / ".bb_session.json"
LOGIN_URL = "https://esprit.blackboard.com/"

# Dossier racine OBLIGATOIRE dans chaque cours Blackboard : tout l'upload
# (arborescence du repo) est confiné ici, sans toucher à quoi que ce soit
# d'autre déjà présent dans l'espace du cours.
ROOT_FOLDER = "Passage de grade Aymen Ben Brik"

EXCLUDE_DIRS = {
    ".git", ".github", ".vscode", ".idea",
    "__pycache__", ".venv", "venv", "env",
    "node_modules", ".ipynb_checkpoints",
    ".pytest_cache", ".mypy_cache",
    "build", "_minted-*",
}

EXCLUDE_FILES = {
    # LaTeX
    "*.aux", "*.log", "*.out", "*.toc", "*.nav", "*.snm",
    "*.synctex.gz", "*.fls", "*.fdb_latexmk", "*.vrb",
    "*.lof", "*.lot", "*.bbl", "*.blg", "*.idx", "*.ilg", "*.ind",
    "*.run.xml", "*.bcf",
    # Python
    "*.pyc", "*.pyo",
    # OS
    ".DS_Store", "Thumbs.db", "desktop.ini",
    # Git
    ".gitignore", ".gitattributes", ".gitmodules",
}

# Sélecteurs Blackboard Ultra — à caler au 1er run headed (--debug).
SELECTORS = {
    "logged_in_marker": "[data-analytics-id='base-navigation-courses']",
    "course_outline_root": "bb-base-outline, [data-analytics-id='outline-container']",
    "add_button": "button[aria-label*='Créer'], button[aria-label*='Create']",
    "menu_create_folder": "text=/Dossier|Folder/",
    "menu_upload": "text=/Téléverser|Upload/",
    "folder_name_input": "input[aria-label*='Nom'], input[aria-label*='Name']",
    "save_button": "button:has-text('Enregistrer'), button:has-text('Save')",
    "file_input": "input[type='file']",
    "existing_item_by_title": "[role='listitem'] :text-is('{title}')",
}

# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #

def norm(s: str | None) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).lower()


def parse_formations(cell) -> list[str]:
    if not cell:
        return []
    return [norm(p) for p in re.split(r"[/,;+&]", str(cell)) if p.strip()]


# --------------------------------------------------------------------------- #
# Modèle : Module / État
# --------------------------------------------------------------------------- #

@dataclass
class Module:
    name: str            # "Algèbre 2"
    formation: str       # "LMAD"
    niveau: str          # "L1"
    code: str            # "1M0-A2"
    urls: list[str]      # ["https://esprit.blackboard.com/ultra/courses/_26547_1/outline"]

    @property
    def key(self) -> str:
        return f"{norm(self.name)}|{norm(self.formation)}"

    @property
    def display(self) -> str:
        return f"{self.name} ({self.formation}/{self.niveau})"


def load_modules(xlsx: Path = XLSX_PATH) -> list[Module]:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb.active
    out: list[Module] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        module, formation, niveau, code, url1, url2 = (
            row[0], row[1], row[2], row[3], row[4], row[5]
        )
        if not module:
            continue
        urls = [u for u in (url1, url2) if isinstance(u, str) and u.startswith("http")]
        if not urls:
            continue
        out.append(Module(
            name=str(module).strip(),
            formation=str(formation or "").strip(),
            niveau=str(niveau or "").strip(),
            code=str(code or "").strip(),
            urls=urls,
        ))
    return out


@dataclass
class State:
    modules: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "State":
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return cls(modules=data.get("modules", {}))
        return cls()

    def save(self) -> None:
        STATE_PATH.write_text(
            json.dumps({"modules": self.modules}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str) -> dict:
        return self.modules.setdefault(key, {"status": "pending", "files": {}})

    def set_status(self, key: str, status: str) -> None:
        entry = self.get(key)
        entry["status"] = status
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def mark_file(self, key: str, rel: str, status: str) -> None:
        entry = self.get(key)
        entry["files"][rel] = {"status": status,
                               "at": datetime.now().isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- #
# File walker
# --------------------------------------------------------------------------- #

def _dir_excluded(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_DIRS)


def _file_excluded(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES)


def walk_repo(root: Path) -> Iterable[Path]:
    """Yield absolute paths of files to upload, respectant les exclusions."""
    root = root.resolve()
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        # Exclusions sur tout segment du chemin relatif
        rel_parts = p.relative_to(root).parts
        if any(_dir_excluded(part) for part in rel_parts[:-1]):
            continue
        if _file_excluded(p.name):
            continue
        yield p


def directories_of(files: list[Path], root: Path) -> list[tuple[Path, ...]]:
    """Tuples de chemins relatifs (parent dirs) à créer, ordonnés du moins au plus profond."""
    dirs: set[tuple[str, ...]] = set()
    for f in files:
        parts = f.relative_to(root).parts[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add(parts[:i])
    return sorted(dirs, key=lambda t: (len(t), t))


# --------------------------------------------------------------------------- #
# Sous-commandes CLI
# --------------------------------------------------------------------------- #

def cmd_status(_args) -> int:
    state = State.load()
    modules = load_modules()
    print(f"{'Module':<40} {'Formation':<10} {'Statut':<12} Fichiers")
    print("-" * 80)
    for m in modules:
        entry = state.modules.get(m.key, {"status": "pending", "files": {}})
        n = sum(1 for v in entry.get("files", {}).values()
                if v.get("status") == "uploaded")
        print(f"{m.name:<40} {m.formation:<10} {entry['status']:<12} {n}")
    return 0


def cmd_login(_args) -> int:
    from bb_browser import login  # lazy import (Playwright)
    login(LOGIN_URL, SESSION_PATH, SELECTORS["logged_in_marker"])
    return 0


def _resolve_module(name: str, modules: list[Module]) -> Module:
    nk = norm(name)
    matches = [m for m in modules if norm(m.name) == nk]
    if not matches:
        # match fuzzy par préfixe
        matches = [m for m in modules if norm(m.name).startswith(nk)]
    if not matches:
        sys.exit(f"Module introuvable : {name!r}. Lance `bb_upload.py status` pour voir la liste.")
    if len(matches) > 1:
        print("Plusieurs matches :")
        for i, m in enumerate(matches, 1):
            print(f"  [{i}] {m.display}")
        idx = int(input("Choix : ").strip()) - 1
        return matches[idx]
    return matches[0]


def cmd_upload(args) -> int:
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.exit(f"Dossier introuvable : {repo}")

    modules = load_modules()
    module = _resolve_module(args.module, modules)
    state = State.load()

    files = list(walk_repo(repo))
    if not files:
        sys.exit(f"Aucun fichier (après exclusions) dans {repo}.")

    inner_dirs = directories_of(files, repo)
    # On préfixe TOUT par le dossier racine `Passage de grade Aymen Ben Brik`.
    # Le dossier racine lui-même est créé en premier, puis chaque sous-arborescence.
    dirs = [(ROOT_FOLDER,)] + [(ROOT_FOLDER, *d) for d in inner_dirs]

    print(f"\n→ {module.display}")
    print(f"  URL : {module.urls[0]}")
    print(f"  Repo : {repo}")
    print(f"  Dossier racine Blackboard : {ROOT_FOLDER}/")
    print(f"  Dossiers à créer : {len(dirs)}  (dont la racine)")
    print(f"  Fichiers à uploader : {len(files)}")
    if args.dry_run:
        for d in dirs:
            print("  DIR ", "/".join(d))
        for f in files:
            rel = f.relative_to(repo)
            print("  FILE", f"{ROOT_FOLDER}/{rel.as_posix()}")
        return 0
    if not args.yes:
        if input("Continuer ? [Y/n] ").strip().lower() not in ("", "y", "o", "yes", "oui"):
            return 1

    state.set_status(module.key, "in_progress")
    state.save()

    from bb_browser import upload_module  # lazy import
    upload_module(
        course_url=module.urls[0],
        repo_root=repo,
        files=files,
        dirs=dirs,
        root_folder=ROOT_FOLDER,
        session_path=SESSION_PATH,
        selectors=SELECTORS,
        headed=args.headed,
        on_file_done=lambda rel, status: (state.mark_file(module.key, rel, status), state.save()),
    )

    print(f"\nVérifie dans Blackboard : {module.urls[0]}")
    if args.yes or input("Valider ce module ? [Y/n] ").strip().lower() in ("", "y", "o", "yes", "oui"):
        state.set_status(module.key, "validated")
        state.save()
        print(f"✓ {module.name} validé.")
    return 0


def cmd_next(args) -> int:
    state = State.load()
    modules = load_modules()
    pending = [m for m in modules
               if state.modules.get(m.key, {}).get("status", "pending") != "validated"]
    if not pending:
        print("Tous les modules sont validés.")
        return 0
    m = pending[0]
    print(f"Prochain module : {m.display}")
    print(f"URL : {m.urls[0]}")
    repo = input("Chemin local du repo : ").strip().strip('"')
    args.module = m.name
    args.repo = repo
    args.dry_run = False
    args.yes = False
    args.headed = getattr(args, "headed", False)
    return cmd_upload(args)


def cmd_probe(args) -> int:
    modules = load_modules()
    module = _resolve_module(args.module, modules)
    out = Path(args.out or (Path.cwd() / f"bb_probe_{norm(module.name).replace(' ', '_')}.html"))
    from bb_browser import probe_course
    probe_course(
        course_url=module.urls[0],
        session_path=SESSION_PATH,
        out_html=out,
        headed=True,
    )
    return 0


def cmd_reset(args) -> int:
    state = State.load()
    modules = load_modules()
    m = _resolve_module(args.module, modules)
    state.modules.pop(m.key, None)
    state.save()
    print(f"État de {m.name} réinitialisé.")
    return 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> int:
    p = argparse.ArgumentParser(prog="bb_upload")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Liste modules + statut").set_defaults(func=cmd_status)
    sub.add_parser("login", help="Connexion Blackboard interactive").set_defaults(func=cmd_login)

    pu = sub.add_parser("upload", help="Upload un module")
    pu.add_argument("module")
    pu.add_argument("repo")
    pu.add_argument("--dry-run", action="store_true")
    pu.add_argument("--yes", "-y", action="store_true")
    pu.add_argument("--headed", action="store_true", help="Navigateur visible")
    pu.set_defaults(func=cmd_upload)

    pn = sub.add_parser("next", help="Module pending suivant")
    pn.add_argument("--headed", action="store_true")
    pn.set_defaults(func=cmd_next)

    pp = sub.add_parser("probe", help="Ouvre un cours et dump le HTML pour caler les sélecteurs")
    pp.add_argument("module")
    pp.add_argument("--out", default=None, help="Chemin du fichier HTML de sortie")
    pp.set_defaults(func=cmd_probe)

    pr = sub.add_parser("reset", help="Repasse un module à pending")
    pr.add_argument("module")
    pr.set_defaults(func=cmd_reset)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
