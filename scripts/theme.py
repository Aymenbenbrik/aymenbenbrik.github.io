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


def evolution_bar(df, titre, palette):
    """Barres empilées par année et niveau (évolution temporelle)."""
    import plotly.express as px
    ag = df.groupby(["annee", "niveau"]).size().reset_index(name="count").sort_values("annee")
    fig = px.bar(ag, x="annee", y="count", color="niveau", text="count",
                 title=titre, barmode="stack", color_discrete_sequence=palette)
    fig.update_traces(textposition="inside")
    fig.update_xaxes(categoryorder="category ascending", tickangle=-45)
    return base_layout(fig, height=380)


def evolution_cumul(df, titre, couleur, fond):
    """Courbe cumulée au fil des années (évolution temporelle)."""
    import plotly.graph_objects as go
    ag = df.groupby("annee").size().sort_index().cumsum()
    fig = go.Figure(go.Scatter(x=list(ag.index), y=list(ag.values),
                               mode="lines+markers+text", text=list(ag.values),
                               textposition="top center", textfont=dict(size=10),
                               line=dict(color=couleur, width=3),
                               marker=dict(size=7),
                               fill="tozeroy", fillcolor=fond))
    fig.update_layout(title=titre)
    fig.update_xaxes(tickangle=-45)
    fig.update_yaxes(rangemode="tozero")
    return base_layout(fig, height=380)
