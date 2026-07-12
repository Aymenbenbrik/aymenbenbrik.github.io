"""Tokens de design partages — source unique pour les graphiques.

Miroir Python de styles.scss : toute page qui trace un graphique importe
d'ici sa palette et son layout de base, au lieu de les redefinir.

Usage dans un .qmd (depuis la racine du site) :
    import sys; sys.path.insert(0, "scripts")
    from theme import ESPRIT, base_layout
(depuis un sous-dossier : sys.path.insert(0, "../scripts"))
"""

# Couleurs (voir styles.scss)
ESB_RED = "#C8102E"
INK = "#1F2430"
SLATE = "#5B6472"
MIST = "#F6F7F9"
LINE = "#E6E8EC"

# Sequence categorielle des graphiques
ESPRIT = [ESB_RED, "#4A4A4A", "#0277BD", "#2E7D32", "#F57C00",
          "#6A1B9A", "#00838F", "#5D4037", "#AD1457", "#1565C0"]

FONT = "Inter, sans-serif"
FONT_MONO = "JetBrains Mono, Consolas, monospace"


def base_layout(fig, height=320):
    """Layout plotly standard du site."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family=FONT, size=11, color=INK),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
    )
    return fig
