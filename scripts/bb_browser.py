"""
bb_browser.py — Couche Playwright pour bb_upload.py.

Trois fonctions exposées :
    - login(login_url, session_path, logged_in_marker)
    - upload_module(course_url, repo_root, files, dirs, session_path,
                    selectors, headed, on_file_done)
    - (helpers internes)

Les sélecteurs Blackboard Ultra sont passés par bb_upload.py (constante SELECTORS).
Premier run : utiliser --headed et observer pour caler ces sélecteurs.

Auteur : Aymen Ben Brik
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

try:
    from playwright.sync_api import (
        sync_playwright,
        Browser,
        BrowserContext,
        Page,
        TimeoutError as PWTimeout,
    )
except ImportError:
    sys.exit(
        "Playwright manquant.\n"
        "  pip install playwright\n"
        "  playwright install chromium"
    )


DEFAULT_TIMEOUT_MS = 30_000


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #

def login(login_url: str, session_path: Path, logged_in_marker: str) -> None:
    """Ouvre Chromium headed, attend la confirmation manuelle, sauvegarde la session.

    L'utilisateur se connecte dans la fenêtre puis tape `Entrée` dans le terminal
    pour signaler que c'est bon. Plus robuste que d'essayer de détecter un
    sélecteur spécifique (l'UI Blackboard Ultra change selon les versions).
    """
    print(f"Ouverture de {login_url}")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(login_url)
        print()
        print(">>> Connecte-toi à Blackboard dans la fenêtre Chromium.")
        print(">>> Une fois la page d'accueil chargée, reviens ici et appuie sur Entrée.")
        try:
            input(">>> [Entrée pour sauvegarder la session, Ctrl+C pour annuler] ")
        except (EOFError, KeyboardInterrupt):
            sys.exit("\nAnnulé.")
        # Capture les cookies + localStorage du contexte courant
        ctx.storage_state(path=str(session_path))
        print(f"✓ Session sauvegardée → {session_path}")
        browser.close()


# --------------------------------------------------------------------------- #
# Upload module
# --------------------------------------------------------------------------- #

def probe_course(
    *,
    course_url: str,
    session_path: Path,
    out_html: Path,
    headed: bool = True,
) -> None:
    """Ouvre un cours, attend qu'il charge, dump le HTML pour inspection des sélecteurs."""
    if not session_path.exists():
        sys.exit("Pas de session : lance d'abord `bb_upload.py login`.")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        ctx = browser.new_context(storage_state=str(session_path))
        ctx.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = ctx.new_page()
        page.goto(course_url)
        print(f"Page chargée. Laisse-moi 8s pour que Ultra finisse de monter le DOM...")
        page.wait_for_load_state("networkidle", timeout=30_000)
        time.sleep(8)
        html = page.content()
        out_html.write_text(html, encoding="utf-8")
        print(f"✓ HTML sauvegardé ({len(html):,} octets) → {out_html}")
        print(">>> Inspecte la page dans Chromium (le DOM est encore visible).")
        print(">>> Appuie sur Entrée pour fermer.")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        browser.close()


def upload_module(
    *,
    course_url: str,
    repo_root: Path,
    files: list[Path],
    dirs: list[tuple[str, ...]],
    root_folder: str,
    session_path: Path,
    selectors: dict,
    headed: bool,
    on_file_done: Callable[[str, str], None],
) -> None:
    """Crée l'arborescence puis uploade chaque fichier dans son dossier.

    Tout est confiné dans `root_folder` à la racine du cours : aucun autre
    item existant dans le cours n'est lu, modifié ou supprimé.
    `dirs` doit déjà inclure `root_folder` comme premier segment (le caller
    s'en charge dans bb_upload.py).
    """
    if not session_path.exists():
        sys.exit(f"Pas de session : lance d'abord `bb_upload.py login`.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        ctx = browser.new_context(storage_state=str(session_path))
        ctx.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = ctx.new_page()
        page.goto(course_url)

        # Vérifie qu'on est bien connecté
        try:
            page.wait_for_selector(selectors["course_outline_root"], timeout=15_000)
        except PWTimeout:
            sys.exit("Cours non chargé — session peut-être expirée. Relance `login`.")

        # 1) Création des dossiers (du moins au plus profond)
        for d in dirs:
            _ensure_folder_path(page, d, selectors)

        # 2) Upload des fichiers — parent toujours préfixé par root_folder
        total = len(files)
        for i, f in enumerate(files, 1):
            rel = f.relative_to(repo_root).as_posix()
            parent = (root_folder, *f.relative_to(repo_root).parts[:-1])
            try:
                _navigate_to_folder(page, parent, selectors)
                if _file_already_present(page, f.name, selectors):
                    print(f"  [{i}/{total}] SKIP  {rel}")
                    on_file_done(rel, "skipped")
                    continue
                _upload_file(page, f, selectors)
                print(f"  [{i}/{total}] OK    {rel}")
                on_file_done(rel, "uploaded")
            except Exception as e:  # noqa: BLE001
                print(f"  [{i}/{total}] FAIL  {rel} — {e}")
                on_file_done(rel, f"failed: {e}")
            # Retour à la racine du cours entre fichiers (sélecteurs Ultra simples)
            page.goto(course_url)
            page.wait_for_selector(selectors["course_outline_root"])

        ctx.storage_state(path=str(session_path))
        browser.close()


# --------------------------------------------------------------------------- #
# Helpers Blackboard Ultra
# --------------------------------------------------------------------------- #
# NOTE : Ces helpers sont une 1ère approximation. Au 1er run headed, observer
# l'UI réelle et ajuster les sélecteurs / la séquence de clics.

def _ensure_folder_path(page: Page, path_parts: tuple[str, ...], selectors: dict) -> None:
    """Crée chaque segment du chemin s'il n'existe pas (depuis la racine)."""
    # Pour l'instant : implémentation linéaire, retour racine entre chaque niveau
    for depth in range(1, len(path_parts) + 1):
        parents = path_parts[:depth - 1]
        new_name = path_parts[depth - 1]
        _navigate_to_folder(page, parents, selectors)
        if not _folder_exists_here(page, new_name, selectors):
            _create_folder_here(page, new_name, selectors)


def _navigate_to_folder(page: Page, parts: tuple[str, ...], selectors: dict) -> None:
    """Re-ouvre les dossiers depuis la racine du cours."""
    for name in parts:
        # Click sur le dossier portant ce nom
        page.locator(f"text=/^{_escape_regex(name)}$/").first.click()
        time.sleep(0.4)  # let UI animate


def _folder_exists_here(page: Page, name: str, selectors: dict) -> bool:
    try:
        return page.locator(f"text=/^{_escape_regex(name)}$/").first.is_visible(timeout=2000)
    except PWTimeout:
        return False


def _file_already_present(page: Page, filename: str, selectors: dict) -> bool:
    try:
        return page.locator(f"text=/^{_escape_regex(Path(filename).stem)}$/")\
                   .first.is_visible(timeout=2000)
    except PWTimeout:
        return False


def _create_folder_here(page: Page, name: str, selectors: dict) -> None:
    """Clic sur + → 'Créer un dossier' → saisir le nom → Enregistrer."""
    page.locator(selectors["add_button"]).first.click()
    page.locator(selectors["menu_create_folder"]).first.click()
    page.locator(selectors["folder_name_input"]).first.fill(name)
    page.locator(selectors["save_button"]).first.click()
    page.wait_for_load_state("networkidle")


def _upload_file(page: Page, file: Path, selectors: dict) -> None:
    """Clic sur + → Téléverser → choisir fichier → Enregistrer."""
    page.locator(selectors["add_button"]).first.click()
    with page.expect_file_chooser() as fc_info:
        page.locator(selectors["menu_upload"]).first.click()
    fc_info.value.set_files(str(file))
    page.wait_for_load_state("networkidle", timeout=120_000)
    # Bouton Enregistrer s'il y a un formulaire d'édition
    try:
        page.locator(selectors["save_button"]).first.click(timeout=5_000)
        page.wait_for_load_state("networkidle")
    except PWTimeout:
        pass


def _escape_regex(s: str) -> str:
    return s.replace("\\", "\\\\").replace(".", "\\.").replace("(", "\\(")\
            .replace(")", "\\)").replace("[", "\\[").replace("]", "\\]")\
            .replace("+", "\\+").replace("?", "\\?").replace("*", "\\*")\
            .replace("/", "\\/").replace("$", "\\$").replace("^", "\\^")
