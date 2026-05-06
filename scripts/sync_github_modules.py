"""
Synchronise le contenu des dépôts GitHub des cours dans les fiches modules.

Pour chaque module listé dans `Passage de grade/Enseignement.xlsx` ayant un
`Lien du module`, le script clone le dépôt en shallow (`git clone --depth 1`)
dans un répertoire temporaire puis en extrait :
  - le README
  - l'arborescence (filtrée sur les supports : PDF, TeX, ipynb, py, csv,
    docx, pptx, xlsx, zip, md autres que README)

Il injecte alors un bloc auto-généré dans la fiche catalogue correspondante
`enseignements/modules/<slug>.qmd`, entre les marqueurs sentinelles
`<!-- BEGIN_GITHUB_AUTO -->` et `<!-- END_GITHUB_AUTO -->`. Le script est
idempotent : ré-exécutable sans dupliquer le bloc.

Ordre recommandé d'exécution si l'on régénère tout :
    1. python scripts/generate_module_pages.py   (squelette des 43 fiches)
    2. python scripts/sync_github_modules.py     (injection GitHub)

Le clone passe par git, sans authentification (dépôts publics). Aucun appel
à l'API REST GitHub n'est effectué, ce qui évite la limite de 60 req/h des
requêtes anonymes.

Auteur : Aymen Ben Brik <aymen.benbrik@esprit.tn>
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = Path(r"C:\Users\aymen\OneDrive\Bureau\Passage de grade\Enseignement.xlsx")
CATALOG_DIR = ROOT / "enseignements" / "modules"
INDEX_FILE = CATALOG_DIR / "index.qmd"

BEGIN = "<!-- BEGIN_GITHUB_AUTO -->"
END = "<!-- END_GITHUB_AUTO -->"

EXT_LABEL = {
    ".pdf": "PDF",
    ".tex": "LaTeX",
    ".ipynb": "Notebook",
    ".py": "Python",
    ".r": "R",
    ".rmd": "R Markdown",
    ".csv": "CSV",
    ".xlsx": "Excel",
    ".docx": "Word",
    ".pptx": "PowerPoint",
    ".zip": "Archive",
    ".md": "Markdown",
}
KEEP_EXT = set(EXT_LABEL)


def parse_repos_from_cell(cell: str) -> list[str]:
    """Une cellule peut contenir plusieurs liens (un bare `org/repo`,
    ou une URL https://github.com/...). On en extrait la liste."""
    out: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[\s,]+", str(cell).strip()):
        token = token.strip()
        if not token:
            continue
        if token.startswith("http"):
            m = re.match(r"https?://github\.com/([^/]+/[^/?#]+)", token)
            if m:
                repo = m.group(1).removesuffix(".git")
            else:
                continue
        elif "/" in token and not token.startswith("/"):
            repo = token
        else:
            continue
        if repo not in seen:
            seen.add(repo)
            out.append(repo)
    return out


def build_slug_map() -> dict[str, str]:
    """Lit `enseignements/modules/index.qmd` pour récupérer la table
    {nom de module → slug du fichier .qmd}."""
    txt = INDEX_FILE.read_text(encoding="utf-8")
    return {
        name.strip(): slug
        for name, slug in re.findall(r"\[([^\]]+)\]\(([\w\-]+)\.qmd\)", txt)
    }


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def fetch_repo(repo: str) -> dict | None:
    """Clone shallow le dépôt et lit le README + l'arborescence localement."""
    url = f"https://github.com/{repo}.git"
    tmp = Path(tempfile.mkdtemp(prefix="ghmod-"))
    try:
        # --filter=blob:none évite de télécharger les blobs non-checkout-és
        # mais reste compatible avec un checkout shallow normal pour lecture.
        res = _git([
            "clone", "--depth", "1", "--single-branch",
            "--no-tags", "--quiet", url, str(tmp),
        ])
        if res.returncode != 0:
            print(f"    ! clone {repo} échoué : {res.stderr.strip()[:200]}")
            return None
        # Branche
        head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp).stdout.strip()
        branch = head or "main"
        # README (variantes : README.md, README.MD, Readme.md, README, README.rst)
        readme = None
        for cand in ("README.md", "README.MD", "Readme.md", "readme.md", "README", "README.rst"):
            p = tmp / cand
            if p.is_file():
                readme = p.read_text(encoding="utf-8", errors="replace")
                break
        # Arborescence via git ls-tree (chemins POSIX)
        ls = _git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=tmp)
        files = [{"path": line.strip()} for line in ls.stdout.splitlines() if line.strip()]
        # On n'a pas de description côté git ; on la laisse vide.
        return {
            "info": {"html_url": f"https://github.com/{repo}", "description": ""},
            "branch": branch,
            "readme": readme,
            "files": files,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_supports(repo: str, branch: str, files: list[dict]) -> str:
    """Liste markdown des supports, groupés par dossier de premier niveau."""
    relevant: list[str] = []
    for f in files:
        path = f["path"]
        ext = Path(path).suffix.lower()
        if ext not in KEEP_EXT:
            continue
        if Path(path).name.lower() == "readme.md":
            continue
        relevant.append(path)
    if not relevant:
        return "_Aucun support listé pour ce dépôt._"
    by_folder: dict[str, list[str]] = {}
    for path in relevant:
        parts = Path(path).parts
        folder = parts[0] if len(parts) > 1 else "(racine)"
        by_folder.setdefault(folder, []).append(path)
    lines: list[str] = []
    for folder in sorted(by_folder):
        lines.append("")
        lines.append(f"**{folder}**")
        lines.append("")
        for path in sorted(by_folder[folder]):
            ext = Path(path).suffix.lower()
            label = EXT_LABEL.get(ext, ext.lstrip("."))
            quoted = urllib.parse.quote(path)
            url = f"https://github.com/{repo}/blob/{branch}/{quoted}"
            lines.append(f"- {label} — [{Path(path).name}]({url})")
    return "\n".join(lines).strip()


def _rewrite_relative_links(md: str, repo: str, branch: str) -> str:
    """Réécrit les liens markdown relatifs `[…](path)` et images
    `![…](path)` vers des URLs GitHub absolues, pour qu'ils restent
    cliquables une fois inclus dans la fiche Quarto."""
    base_blob = f"https://github.com/{repo}/blob/{branch}/"
    base_raw = f"https://raw.githubusercontent.com/{repo}/{branch}/"

    def is_external(url: str) -> bool:
        return (
            url.startswith(("http://", "https://", "mailto:", "ftp://", "#"))
            or url.startswith("/")
        )

    def repl_link(m: re.Match) -> str:
        bang, text, url, title = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        if is_external(url):
            return m.group(0)
        url = url.split("#", 1)
        anchor = ("#" + url[1]) if len(url) > 1 else ""
        path = urllib.parse.quote(url[0])
        target = (base_raw if bang else base_blob) + path + anchor
        return f"{bang}[{text}]({target}{title})"

    pattern = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
    return pattern.sub(repl_link, md)


def shift_readme_headings(md: str, levels: int = 2) -> str:
    """Décale toutes les # (hors blocs ``` ... ```) de `levels` niveaux pour
    que le README s'insère sous `## README` sans perturber la TOC."""
    out: list[str] = []
    in_code = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if not in_code:
            m = re.match(r"^(#{1,6})\s", line)
            if m:
                hashes = m.group(1)
                new = "#" * min(6, len(hashes) + levels)
                line = new + line[len(hashes):]
        out.append(line)
    return "\n".join(out)


def normalize_readme(md: str, repo: str, branch: str) -> str:
    return shift_readme_headings(_rewrite_relative_links(md, repo, branch))


def build_block(repos: list[str], data: dict[str, dict]) -> str:
    parts: list[str] = [BEGIN, "", "## Dépôt GitHub", ""]
    for r in repos:
        info = data[r]["info"]
        url = info.get("html_url", f"https://github.com/{r}")
        desc = (info.get("description") or "").strip()
        line = f"- [`{r}`]({url})"
        if desc:
            line += f" — {desc}"
        parts.append(line)
    parts += ["", "## Supports pédagogiques", ""]
    for r in repos:
        if len(repos) > 1:
            parts.append(f"### `{r}`")
            parts.append("")
        parts.append(render_supports(r, data[r]["branch"], data[r]["files"]))
        parts.append("")
    parts += ["## README du dépôt", ""]
    for r in repos:
        if len(repos) > 1:
            parts.append(f"### `{r}`")
            parts.append("")
        rm = data[r]["readme"]
        if rm:
            parts.append(normalize_readme(rm, r, data[r]["branch"]))
        else:
            parts.append("_Pas de README disponible._")
        parts.append("")
    parts.append(END)
    return "\n".join(parts)


# Ancienne queue à remplacer dans les fiches catalogue (générées par
# generate_module_pages.py) si pas encore enrichies. On capture depuis le
# titre "## Code & supports sur GitHub" jusqu'au callout final exclu, ou
# jusqu'à la fin du fichier.
LEGACY_TAIL = re.compile(
    r"\n## Code & supports sur GitHub.*?(?=\n---\n\n::: \{\.callout-note\}|\Z)",
    re.DOTALL,
)


def update_qmd(path: Path, block: str) -> bool:
    txt = path.read_text(encoding="utf-8")
    # Les remplacements sont passés via lambda pour traiter `block`
    # littéralement (le README peut contenir \m, \b, \1… qui sont des
    # séquences spéciales pour re.sub si on lui passe une chaîne).
    if BEGIN in txt and END in txt:
        new = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END),
            lambda _m: block,
            txt,
            count=1,
            flags=re.DOTALL,
        )
    elif LEGACY_TAIL.search(txt):
        new = LEGACY_TAIL.sub(lambda _m: "\n" + block, txt)
    else:
        # Insère avant le dernier callout-note s'il existe, sinon en fin
        m = re.search(r"\n---\n\n::: \{\.callout-note\}", txt)
        if m:
            new = txt[: m.start()] + "\n\n" + block + "\n" + txt[m.start():]
        else:
            new = txt.rstrip() + "\n\n" + block + "\n"
    if new != txt:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> int:
    if not XLSX.exists():
        print(f"!! Introuvable : {XLSX}", file=sys.stderr)
        return 1
    df = pd.read_excel(XLSX, sheet_name="Module ", header=3, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    sub = df[["Module", "Lien du module"]].dropna(subset=["Lien du module"])
    sub["Module"] = sub["Module"].astype(str).str.strip()
    sub["Lien du module"] = sub["Lien du module"].astype(str).str.strip()

    slug_map = build_slug_map()
    print(f"Catalog: {len(slug_map)} slugs")

    seen_modules: set[str] = set()
    modules_with_link: list[tuple[str, str]] = []
    for _, row in sub.iterrows():
        m = row["Module"]
        if m in seen_modules:
            continue
        seen_modules.add(m)
        modules_with_link.append((m, row["Lien du module"]))
    print(f"Modules avec lien GitHub : {len(modules_with_link)}")

    repo_cache: dict[str, dict | None] = {}

    def get_repo(r: str) -> dict | None:
        if r not in repo_cache:
            print(f"  fetch {r}…")
            try:
                repo_cache[r] = fetch_repo(r)
            except Exception as exc:  # pragma: no cover
                print(f"    ! {r}: {exc}")
                repo_cache[r] = None
        return repo_cache[r]

    updated = unchanged = skipped = 0
    for module, cell in modules_with_link:
        slug = slug_map.get(module)
        if not slug:
            print(f"  ? slug introuvable pour {module!r}")
            skipped += 1
            continue
        target = CATALOG_DIR / f"{slug}.qmd"
        if not target.exists():
            print(f"  ? fiche absente : {target}")
            skipped += 1
            continue
        repos = parse_repos_from_cell(cell)
        data: dict[str, dict] = {}
        for r in repos:
            d = get_repo(r)
            if d is not None:
                data[r] = d
        if not data:
            skipped += 1
            continue
        block = build_block([r for r in repos if r in data], data)
        if update_qmd(target, block):
            print(f"  ✓ {slug}.qmd  ({', '.join(data)})")
            updated += 1
        else:
            print(f"  · {slug}.qmd inchangé")
            unchanged += 1

    print(f"\nTotal — modifiés : {updated} · inchangés : {unchanged} · ignorés : {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
