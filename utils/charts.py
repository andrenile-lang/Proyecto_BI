"""Gráficos Plotly con identidad visual coherente."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

RED, ORANGE, YELLOW, GREEN, DARK, GREY = "#C0392B", "#E67E22", "#F4B41A", "#2E7D32", "#2B2B2B", "#8A8A8A"
SEQ = [RED, ORANGE, YELLOW, GREEN, "#6D4C41", "#455A64", "#AD1457", "#00838F"]
LAYOUT = dict(template="plotly_white", font=dict(family="Segoe UI, Arial", size=12), margin=dict(l=10, r=10, t=45, b=10),
              colorway=SEQ, title_font=dict(size=15), legend=dict(orientation="h", y=-0.15))


def _fmt(fig, title=None, h=360):
    fig.update_layout(**LAYOUT, height=h)
    if title:
        fig.update_layout(title=title)
    return fig


def line_monthly(m: pd.DataFrame, color=None, title="Ventas y utilidad mensual (USD)"):
    if color:
        fig = px.line(m, x="Periodo", y="Ventas", color=color, markers=True)
    else:
        fig = go.Figure()
        fig.add_scatter(x=m["Periodo"], y=m["Ventas"], name="Ventas", mode="lines+markers", line=dict(color=RED, width=3))
        fig.add_scatter(x=m["Periodo"], y=m["Utilidad"], name="Utilidad bruta", mode="lines+markers", line=dict(color=GREEN, width=3))
    fig.update_yaxes(tickprefix="$", separatethousands=True, rangemode="tozero")
    return _fmt(fig, title)


def bar_h(df, x, y, title, color=RED, fmt="$", n=10, text=True):
    d = df.sort_values(x, ascending=False).head(n).sort_values(x)
    fig = go.Figure(go.Bar(x=d[x], y=d[y], orientation="h", marker_color=color,
                           text=d[x].map(lambda v: f"${v:,.0f}" if fmt == "$" else f"{v:.1%}"), textposition="outside"))
    fig.update_xaxes(showgrid=False, visible=False)
    fig.update_layout(yaxis=dict(automargin=True))
    return _fmt(fig, title, h=max(300, 30 * len(d) + 80))


def bar_v(df, x, y, title, color=None, fmt="$", sort=True, h=340):
    d = df.sort_values(y, ascending=False) if sort else df
    fig = px.bar(d, x=x, y=y, color=color, text=d[y].map(lambda v: f"${v:,.0f}" if fmt == "$" else f"{v:.1%}"))
    if color is None:
        fig.update_traces(marker_color=RED)
    fig.update_traces(textposition="outside")
    fig.update_yaxes(visible=False)
    return _fmt(fig, title, h=h)


def donut(df, names, values, title):
    fig = px.pie(df, names=names, values=values, hole=0.55, color_discrete_sequence=SEQ)
    fig.update_traces(textinfo="percent+label", textposition="outside")
    fig.update_layout(showlegend=False)
    return _fmt(fig, title, h=340)


def pareto(pt: pd.DataFrame, title="Pareto de productos: ventas y % acumulado"):
    fig = go.Figure()
    fig.add_bar(x=pt["Producto"], y=pt["Ventas"], name="Ventas", marker_color=RED)
    fig.add_scatter(x=pt["Producto"], y=pt["%Acum"], name="% acumulado", yaxis="y2", mode="lines+markers", line=dict(color=DARK))
    fig.add_hline(y=0.8, yref="y2", line_dash="dot", line_color=GREY, annotation_text="80%")
    fig.update_layout(yaxis=dict(tickprefix="$"), yaxis2=dict(overlaying="y", side="right", tickformat=".0%", range=[0, 1.02], showgrid=False),
                      xaxis=dict(tickangle=-60))
    return _fmt(fig, title, h=420)


def product_scatter(pt: pd.DataFrame, title="Matriz de productos: ventas vs. margen (tamaño = utilidad)"):
    fig = px.scatter(pt, x="Ventas", y="Margen", size="Utilidad", color="Decisión", hover_name="Producto",
                     color_discrete_map={"Potenciar": GREEN, "Revisar costo/precio": RED, "Impulsar demanda": YELLOW, "Revisar permanencia": GREY},
                     size_max=38)
    tm = pt["Utilidad"].sum() / pt["Ventas"].sum() if pt["Ventas"].sum() else 0
    fig.add_hline(y=tm, line_dash="dot", line_color=GREY, annotation_text="margen global")
    fig.add_vline(x=pt["Ventas"].median(), line_dash="dot", line_color=GREY, annotation_text="mediana ventas")
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickprefix="$", separatethousands=True)
    return _fmt(fig, title, h=440)


def branch_bars(br: pd.DataFrame, title="Ventas por sucursal (color = margen bruto)"):
    d = br.sort_values("Ventas")
    fig = go.Figure(go.Bar(x=d["Ventas"], y=d["Sucursal"], orientation="h",
                           marker=dict(color=d["Margen"], colorscale=[[0, RED], [1, GREEN]], colorbar=dict(title="Margen", tickformat=".0%")),
                           text=d["Ventas"].map(lambda v: f"${v:,.0f}"), textposition="outside"))
    fig.update_xaxes(visible=False)
    return _fmt(fig, title, h=380)


def score_bars(br: pd.DataFrame, title="Score compuesto por sucursal (0–100)"):
    d = br.sort_values("Score")
    fig = go.Figure(go.Bar(x=d["Score"], y=d["Sucursal"], orientation="h",
                           marker_color=[GREEN if i == len(d) - 1 else (RED if i == 0 else ORANGE) for i in range(len(d))],
                           text=d["Score"].map(lambda v: f"{v:.0f}"), textposition="outside"))
    fig.update_xaxes(range=[0, 110], visible=False)
    return _fmt(fig, title, h=380)


def discount_margin(dt: pd.DataFrame, title="Margen bruto y ticket según nivel de descuento"):
    fig = go.Figure()
    fig.add_bar(x=dt["Descuento"], y=dt["Margen"], name="Margen bruto", marker_color=RED, text=dt["Margen"].map(lambda v: f"{v:.1%}"), textposition="outside")
    fig.add_scatter(x=dt["Descuento"], y=dt["Ticket"], name="Ticket (USD)", yaxis="y2", mode="lines+markers", line=dict(color=DARK))
    fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 0.8]), yaxis2=dict(overlaying="y", side="right", tickprefix="$", showgrid=False))
    return _fmt(fig, title)


def heat(df: pd.DataFrame, index, columns, values, title, fmt=",.0f"):
    p = df.pivot_table(index=index, columns=columns, values=values, aggfunc="sum")
    fig = px.imshow(p, text_auto=fmt, aspect="auto", color_continuous_scale=["#FFF3E0", ORANGE, RED])
    return _fmt(fig, title, h=360)
