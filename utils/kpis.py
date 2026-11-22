"""Indicadores, rankings y contexto analítico (sin dependencia de Streamlit)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(a, b):
    return float(a) / float(b) if b else 0.0


def kpis(df: pd.DataFrame) -> dict:
    ventas = float(df["VentaNeta"].sum())
    util = float(df["UtilidadBruta"].sum())
    trans = int(df["VentaID"].nunique())
    return {
        "ventas": ventas,
        "utilidad": util,
        "margen": _safe_div(util, ventas),
        "transacciones": trans,
        "clientes": int(df["ClienteID"].nunique()),
        "ticket": _safe_div(ventas, trans),
        "unidades": float(df["Cantidad"].sum()),
        "descuento_usd": float(df["DescuentoUSD"].sum()),
    }


def group_kpis(df: pd.DataFrame, by) -> pd.DataFrame:
    g = df.groupby(by, observed=True).agg(
        Ventas=("VentaNeta", "sum"), Utilidad=("UtilidadBruta", "sum"),
        Transacciones=("VentaID", "nunique"), Clientes=("ClienteID", "nunique"),
        Unidades=("Cantidad", "sum"),
        DescMedio=("DescuentoPct", "mean"),
    ).reset_index()
    g["Margen"] = np.where(g["Ventas"] > 0, g["Utilidad"] / g["Ventas"], 0)
    g["Ticket"] = np.where(g["Transacciones"] > 0, g["Ventas"] / g["Transacciones"], 0)
    tot = g["Ventas"].sum()
    g["%Ventas"] = np.where(tot > 0, g["Ventas"] / tot, 0)
    return g


def yoy_table(df: pd.DataFrame):
    """Compara el último año con el anterior dentro del filtro actual."""
    years = sorted(df["Año"].unique())
    if len(years) < 2:
        return None
    y1, y0 = years[-1], years[-2]
    a, b = kpis(df[df["Año"] == y1]), kpis(df[df["Año"] == y0])
    out = {"y1": y1, "y0": y0}
    for k in ["ventas", "utilidad", "transacciones", "ticket", "clientes"]:
        out[k] = (a[k] / b[k] - 1) if b[k] else 0
    out["margen_pts"] = (a["margen"] - b["margen"]) * 100
    out["a"], out["b"] = a, b
    return out


def yoy_by(df: pd.DataFrame, by: str) -> pd.DataFrame:
    years = sorted(df["Año"].unique())
    if len(years) < 2:
        return pd.DataFrame()
    y1, y0 = years[-1], years[-2]
    p = df[df["Año"].isin([y0, y1])].pivot_table(index=by, columns="Año", values="VentaNeta", aggfunc="sum").fillna(0)
    p["Variación"] = np.where(p[y0] > 0, p[y1] / p[y0] - 1, np.nan)
    p.columns = [str(c) for c in p.columns]
    return p.reset_index()


def monthly(df: pd.DataFrame, by=None) -> pd.DataFrame:
    keys = ["Periodo"] + ([by] if by else [])
    g = group_kpis(df, keys)
    return g.sort_values("Periodo")


def _minmax(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng else pd.Series(0.5, index=s.index)


SCORE_WEIGHTS = {"Ventas": 0.35, "Utilidad": 0.25, "Margen": 0.20, "Ticket": 0.20}


def branch_ranking(df: pd.DataFrame) -> pd.DataFrame:
    g = group_kpis(df, ["Ciudad", "Sucursal"])
    g["Score"] = 100 * sum(w * _minmax(g[k]) for k, w in SCORE_WEIGHTS.items())
    ye = yoy_by(df, "Sucursal")
    if not ye.empty:
        g = g.merge(ye[["Sucursal", "Variación"]].rename(columns={"Variación": "VarAnual"}), on="Sucursal", how="left")
    g["Ranking"] = g["Score"].rank(ascending=False, method="min").astype(int)
    return g.sort_values("Score", ascending=False).reset_index(drop=True)


def product_table(df: pd.DataFrame, by="Producto") -> pd.DataFrame:
    g = group_kpis(df, [by, "Categoria"] if by in ("Producto", "ProductoTam") else by)
    g = g.sort_values("Ventas", ascending=False).reset_index(drop=True)
    g["%Acum"] = g["%Ventas"].cumsum()
    tot_m = g["Utilidad"].sum() / g["Ventas"].sum() if g["Ventas"].sum() else 0
    med_v = g["Ventas"].median()

    def decide(r):
        hi_v, hi_m = r["Ventas"] >= med_v, r["Margen"] >= tot_m
        if hi_v and hi_m:
            return "Potenciar"
        if hi_v and not hi_m:
            return "Revisar costo/precio"
        if (not hi_v) and hi_m:
            return "Impulsar demanda"
        return "Revisar permanencia"

    g["Decisión"] = g.apply(decide, axis=1)
    return g


def catalog_gap(df: pd.DataFrame) -> pd.DataFrame:
    if "MargenPorcentaje" not in df.columns:
        return pd.DataFrame()
    g = df.groupby("Producto").agg(Ventas=("VentaNeta", "sum"), Utilidad=("UtilidadBruta", "sum"),
                                   MargenCat=("MargenPorcentaje", "mean")).reset_index()
    g["MargenReal"] = np.where(g["Ventas"] > 0, g["Utilidad"] / g["Ventas"] * 100, 0)
    g["Brecha (pts)"] = g["MargenReal"] - g["MargenCat"]
    return g.sort_values("Brecha (pts)")


def discount_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Descuento"] = d["DescuentoPct"].round(0).astype(int).astype(str) + "%"
    g = group_kpis(d, "Descuento")
    g["_o"] = g["Descuento"].str.rstrip("%").astype(int)
    return g.sort_values("_o").drop(columns="_o")


def discount_by(df: pd.DataFrame, by: str) -> pd.DataFrame:
    g = df.groupby(by).agg(Transacciones=("VentaID", "nunique"),
                           ConDescuento=("DescuentoPct", lambda s: (s > 0).mean()),
                           DescMedio=("DescuentoPct", "mean"),
                           DescUSD=("DescuentoUSD", "sum"),
                           Ventas=("VentaNeta", "sum"), Utilidad=("UtilidadBruta", "sum")).reset_index()
    g["Margen"] = np.where(g["Ventas"] > 0, g["Utilidad"] / g["Ventas"], 0)
    return g


def delivery_by(df: pd.DataFrame, by: str) -> pd.DataFrame:
    d = df[df["Canal"].astype(str).str.lower().eq("delivery") & df["TiempoEntregaMin"].notna()]
    if d.empty:
        return pd.DataFrame()
    return d.groupby(by).agg(EntregaMin=("TiempoEntregaMin", "mean"),
                             Pct45=("TiempoEntregaMin", lambda s: (s > 45).mean()),
                             Pedidos=("VentaID", "nunique")).reset_index()


def customer_view(df: pd.DataFrame) -> pd.DataFrame:
    """Clientes únicos presentes en el filtro, con sus atributos CRM."""
    cols = [c for c in ["ClienteID", "Segmento", "ClienteActivo", "NPS", "MotivoPerdida", "GastoAcumuladoUSD",
                        "TicketPromedioUSD", "TotalCompras", "CiudadCliente"] if c in df.columns]
    return df[cols].drop_duplicates("ClienteID")


def segment_crm(df: pd.DataFrame) -> pd.DataFrame:
    c = customer_view(df)
    if "ClienteActivo" not in c.columns:
        return pd.DataFrame()
    c = c.copy()
    c["_act"] = c["ClienteActivo"].astype(str).str.lower().isin(["sí", "si", "yes", "true", "1"])
    g = c.groupby("Segmento").agg(Clientes=("ClienteID", "nunique"), Activos=("_act", "mean"),
                                  NPS=("NPS", "mean") if "NPS" in c else ("_act", "mean"),
                                  GastoProm=("GastoAcumuladoUSD", "mean") if "GastoAcumuladoUSD" in c else ("_act", "mean"),
                                  TicketCRM=("TicketPromedioUSD", "mean") if "TicketPromedioUSD" in c else ("_act", "mean")).reset_index()
    g["%Clientes"] = g["Clientes"] / g["Clientes"].sum()
    return g


def churn_reasons(df: pd.DataFrame) -> pd.DataFrame:
    c = customer_view(df)
    if "MotivoPerdida" not in c.columns:
        return pd.DataFrame()
    c = c[c["MotivoPerdida"].notna() & (c["MotivoPerdida"].astype(str).str.strip() != "")]
    g = c.groupby("MotivoPerdida").agg(Clientes=("ClienteID", "nunique")).reset_index().sort_values("Clientes", ascending=False)
    g["%"] = g["Clientes"] / g["Clientes"].sum() if g["Clientes"].sum() else 0
    return g


# ------------------------------------------------------------------ contexto para IA
def build_context(df: pd.DataFrame, filtros: dict | None = None) -> dict:
    k = kpis(df)
    ctx: dict = {"filtros_aplicados": filtros or {}, "periodo": f"{df['Fecha'].min():%Y-%m-%d} a {df['Fecha'].max():%Y-%m-%d}",
                 "kpis": {kk: round(vv, 4) for kk, vv in k.items()}}
    y = yoy_table(df)
    if y:
        ctx["comparativo_anual"] = {"año_actual": int(y["y1"]), "año_previo": int(y["y0"]),
                                    "var_ventas_pct": round(y["ventas"] * 100, 1),
                                    "var_transacciones_pct": round(y["transacciones"] * 100, 1),
                                    "var_ticket_pct": round(y["ticket"] * 100, 1),
                                    "var_margen_pts": round(y["margen_pts"], 2),
                                    "ventas_año_actual": round(y["a"]["ventas"], 0), "ventas_año_previo": round(y["b"]["ventas"], 0)}
    def top(g, n=3):
        return g.round(4).to_dict("records")[:n]
    for name, by in [("ciudades", "Ciudad"), ("segmentos", "Segmento"), ("categorias", "Categoria"), ("canales", "Canal")]:
        g = group_kpis(df, by).sort_values("Ventas", ascending=False)
        ctx[name] = top(g[[by, "Ventas", "Utilidad", "Margen", "Ticket", "%Ventas"]], 10)
    br = branch_ranking(df)
    cols = [c for c in ["Sucursal", "Ciudad", "Ventas", "Utilidad", "Margen", "Ticket", "Score", "VarAnual"] if c in br.columns]
    ctx["sucursales_ranking"] = br[cols].round(4).to_dict("records")
    pt = product_table(df)
    ctx["productos_top_ventas"] = pt.head(5)[["Producto", "Ventas", "Utilidad", "Margen"]].round(4).to_dict("records")
    ctx["productos_menor_margen"] = pt.sort_values("Margen").head(5)[["Producto", "Ventas", "Margen"]].round(4).to_dict("records")
    ctx["productos_menor_venta"] = pt.sort_values("Ventas").head(3)[["Producto", "Ventas", "Margen"]].round(4).to_dict("records")
    ctx["productos_para_80pct_ventas"] = int((pt["%Acum"] < 0.8).sum() + 1)
    ctx["total_productos"] = int(len(pt))
    ctx["descuentos_por_ciudad"] = discount_by(df, "Ciudad").round(4).to_dict("records")
    ctx["descuentos_por_nivel"] = discount_table(df)[["Descuento", "Transacciones", "Margen", "Ticket"]].round(4).to_dict("records")
    dl = delivery_by(df, "Ciudad")
    if not dl.empty:
        ctx["entrega_delivery_por_ciudad"] = dl.round(3).to_dict("records")
    sc = segment_crm(df)
    if not sc.empty:
        ctx["segmentos_crm"] = sc.round(3).to_dict("records")
        cr = churn_reasons(df)
        if not cr.empty:
            ctx["motivos_perdida_clientes"] = cr.round(3).to_dict("records")
        cv = customer_view(df)
        ctx["clientes_activos_pct"] = round(float(cv["ClienteActivo"].astype(str).str.lower().isin(["sí", "si"]).mean()), 4) if "ClienteActivo" in cv else None
    ya = yoy_by(df, "Ciudad")
    if not ya.empty:
        ctx["var_anual_ventas_por_ciudad"] = ya.round(4).to_dict("records")
    return ctx


def rule_based_recs(ctx: dict) -> str:
    """Motor de respaldo (sin LLM): genera recomendaciones a partir del contexto. Se activa si no hay API key."""
    L = []
    k = ctx["kpis"]
    L.append("### Hallazgos clave (motor de reglas — sin LLM)")
    ca = ctx.get("comparativo_anual")
    if ca:
        L.append(f"- Las ventas de {ca['año_actual']} variaron **{ca['var_ventas_pct']:+.1f}%** frente a {ca['año_previo']} "
                 f"(transacciones {ca['var_transacciones_pct']:+.1f}%, ticket {ca['var_ticket_pct']:+.1f}%). "
                 + ("El problema es de **tráfico**, no de ticket." if abs(ca['var_transacciones_pct']) > abs(ca['var_ticket_pct']) * 2 and ca['var_ventas_pct'] < 0 else ""))
    L.append(f"- Ventas {k['ventas']:,.0f} USD, utilidad {k['utilidad']:,.0f} USD, margen **{k['margen']*100:.1f}%**, ticket {k['ticket']:.2f} USD.")
    br = ctx["sucursales_ranking"]
    L.append(f"- Mejor sucursal: **{br[0]['Sucursal']}** (score {br[0]['Score']:.0f}); peor: **{br[-1]['Sucursal']}** (score {br[-1]['Score']:.0f}).")
    dc = ctx.get("descuentos_por_ciudad", [])
    risks, dec = [], []
    if dc:
        avg = np.mean([d["DescMedio"] for d in dc])
        for d in dc:
            if d["DescMedio"] > 2 * avg and d["DescMedio"] > 3:
                risks.append(f"**{d['Ciudad']}** otorga descuento medio de {d['DescMedio']:.1f}% (promedio de las demás ≈ {np.mean([x['DescMedio'] for x in dc if x['Ciudad']!=d['Ciudad']]):.1f}%) y su margen es {d['Margen']*100:.1f}%.")
                dec.append(f"Reemplazar los descuentos amplios de {d['Ciudad']} por promociones selectivas con tope y medir el efecto en tráfico (evidencia: descuento medio {d['DescMedio']:.1f}%).")
    en = ctx.get("entrega_delivery_por_ciudad", [])
    if en:
        m = np.median([e["EntregaMin"] for e in en])
        for e in en:
            if e["EntregaMin"] > 1.2 * m:
                risks.append(f"Tiempo de entrega en **{e['Ciudad']}** de {e['EntregaMin']:.0f} min vs mediana {m:.0f} min ({e['Pct45']*100:.0f}% de pedidos > 45 min).")
                dec.append(f"Plan operativo de entrega en {e['Ciudad']} (rutas, zonas, personal pico) con meta ≤ {m+5:.0f} min.")
    if ctx.get("clientes_activos_pct") is not None and ctx["clientes_activos_pct"] < 0.75:
        risks.append(f"Solo {ctx['clientes_activos_pct']*100:.1f}% de los clientes está activo.")
        mo = ctx.get("motivos_perdida_clientes", [])
        if mo:
            dec.append(f"Programa de reactivación enfocado en el motivo principal de pérdida ({mo[0]['MotivoPerdida']}, {mo[0]['%']*100:.0f}% de los clientes perdidos).")
    pm = ctx["productos_menor_margen"]
    risks.append("Productos de menor margen: " + ", ".join(f"{p['Producto']} ({p['Margen']*100:.1f}%)" for p in pm[:3]) + ".")
    dec.append("Revisar precio/costo de los productos de menor margen y empaquetarlos con productos de alto margen.")
    cat = {c["Categoria"]: c for c in ctx["categorias"]}
    if cat:
        best = max(ctx["categorias"], key=lambda c: c["Margen"])
        dec.append(f"Aumentar el ticket promedio con combos que incluyan **{best['Categoria']}** (mayor margen: {best['Margen']*100:.1f}%, solo {best['%Ventas']*100:.1f}% de las ventas).")
    sg = ctx.get("segmentos_crm", [])
    if sg:
        s = max(sg, key=lambda x: x.get("TicketCRM", 0) or 0)
        dec.append(f"Priorizar crecimiento del segmento **{s['Segmento']}** (ticket CRM {s['TicketCRM']:.0f} USD, NPS {s['NPS']:.1f}, {s['%Clientes']*100:.1f}% de los clientes).")
    L.append("\n### Riesgos")
    L += [f"- {r}" for r in risks] or ["- Sin riesgos críticos detectados por las reglas."]
    L.append("\n### Decisiones sugeridas")
    L += [f"{i+1}. {d}" for i, d in enumerate(dec[:6])]
    L.append("\n> ⚠️ Estas recomendaciones son automáticas y basadas en reglas; deben validarse críticamente antes de incorporarlas a las conclusiones.")
    return "\n".join(L)
