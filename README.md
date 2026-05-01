# Site académique — Aymen Ben Brik

Portfolio académique d'Aymen Ben Brik, Enseignant Formateur à
**Esprit School of Business**, construit avec [Quarto](https://quarto.org)
et publié sur GitHub Pages.

**URL prévue** : `https://aymen-benbrik.github.io`

## Contenu

- Accueil + indicateurs clés
- 5 modules enseignés (Algèbre 2, Algèbre 3, Probabilités, Analyse 4, RO)
- Encadrements (PFE, projets intégrés)
- Recherche (publications, projets RDI)
- Certifications & formations
- Responsabilités pédagogiques et administratives
- Événements (conférences, jurys, formations animées)
- **Dashboards** : évolution annuelle + score grille EFS

## Installation locale

### 1. Installer Quarto

Télécharger l'installeur depuis <https://quarto.org/docs/get-started/>
(version Windows .msi). Tester avec :

```bash
quarto --version
```

### 2. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 3. Prévisualiser localement

```bash
quarto preview
```

Ouvre le site sur `http://localhost:4444` avec rechargement automatique.

### 4. Build statique

```bash
quarto render
```

Le site est généré dans `_site/`.

## Mise à jour des données

Tous les dashboards lisent les CSVs du dossier `data/` :

| Fichier | Contenu |
|---|---|
| `data/enseignements.csv` | Modules, heures, années, filières |
| `data/encadrements.csv` | PFE, projets, étudiants |
| `data/certifications.csv` | Certifications et formations suivies |
| `data/responsabilites.csv` | Responsabilités péda/admin |
| `data/evenements.csv` | Conférences, jurys, formations animées |
| `data/publications.bib` | Publications au format BibTeX |

Mettre à jour un CSV → `git push` → le site se régénère automatiquement
via GitHub Actions.

## Déploiement sur GitHub Pages

### Premier setup (à faire une fois)

1. Créer le repo `aymen-benbrik.github.io` sur GitHub (public)
2. Lier le dossier local :
   ```bash
   git init
   git remote add origin git@github.com:aymen-benbrik/aymen-benbrik.github.io.git
   git add .
   git commit -m "Initial site"
   git branch -M main
   git push -u origin main
   ```
3. Sur GitHub : `Settings` → `Pages` → `Source` = **GitHub Actions**
4. Le workflow `.github/workflows/publish.yml` build et déploie à chaque push

### Mises à jour suivantes

```bash
git add .
git commit -m "Mise à jour des données"
git push
```

Le site est mis à jour automatiquement (~2 minutes).

## Structure du projet

```
Site_Web/
├── _quarto.yml              Config (navigation, thème)
├── styles.scss              Thème custom Esprit (rouge #C8102E)
├── index.qmd                Accueil + KPI
├── cv.qmd                   CV complet
├── enseignements/
│   ├── index.qmd            Vue d'ensemble + dashboard
│   ├── algebre2.qmd
│   ├── algebre3.qmd
│   ├── probabilites.qmd
│   ├── analyse4.qmd
│   └── recherche-operationnelle.qmd
├── encadrements.qmd
├── recherche.qmd
├── certifications.qmd
├── responsabilites.qmd
├── evenements.qmd
├── dashboards/
│   ├── index.qmd
│   ├── evolution.qmd        Timeline 5 ans
│   └── grille-efs.qmd       Score sur la grille de passage de grade
├── data/
│   ├── enseignements.csv
│   ├── encadrements.csv
│   ├── certifications.csv
│   ├── responsabilites.csv
│   ├── evenements.csv
│   └── publications.bib
├── images/
├── requirements.txt
└── .github/workflows/publish.yml
```

## Auteur

Aymen Ben Brik — Enseignant Formateur, Esprit School of Business
[aymen.benbrik@esprit.tn](mailto:aymen.benbrik@esprit.tn)
