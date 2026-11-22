"""San Francisco Crust Pizza — Sistema Inteligente de Apoyo a la Toma de Decisiones.

Ejecutar:  streamlit run app.py
Actualización automática: sustituya la base de Ventas desde la barra lateral (o reemplace el archivo
de /data) y todos los indicadores, gráficos y el asistente de IA se recalculan sin tocar el código.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from utils import ai, charts, data, kpis

st.set_page_config(page_title="SF Crust Pizza · BI", page_icon="🍕", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
 .block-container{padding-top:1.2rem;}
 div[data-testid="stMetric"]{background:#FFF8F0;border:1px solid #F3D9BF;border-radius:12px;padding:10px 14px;}
 div[data-testid="stMetricValue"]{color:#C0392B;font-size:1.65rem;}
 h1,h2,h3{color:#2B2B2B;}
 .small{color:#6b6b6b;font-size:.85rem;}
</style>""", unsafe_allow_html=True)

usd = lambda v: f"${v:,.0f}"
pct = lambda v: f"{v*100:.1f}%"


# ----------------------------------------------------------------------------- carga de datos
@st.cache_data(show_spinner="Procesando bases de datos…")
def load_all(v_bytes: bytes, v_name: str, p_bytes: bytes | None, p_name: str, c_bytes: bytes | None, c_name: str):
    v = data.read_any(v_bytes, v_name)
    p = data.read_any(p_bytes, p_name) if p_bytes else None
    c = data.read_any(c_bytes, c_name) if c_bytes else None
    df, cli, prod, warns, errs = data.build_dataset(v, p, c)
    return df, warns, errs


def pick(uploaded, kind):
    """Archivo cargado por el usuario, o el archivo por defecto de /data."""
    if uploaded is not None:
        return uploaded.getvalue(), uploaded.name
    p = data.find_default(kind)
    return (p.read_bytes(), p.name) if p else (None, "")


with st.sidebar:
    st.markdown("## 🍕 SF Crust Pizza")
    st.caption("Sistema Inteligente de Apoyo a la Toma de Decisiones")
    with st.expander("📥 Actualizar bases de datos", expanded=False):
        st.caption("Cargue una nueva base de **Ventas** y todo se recalcula automáticamente. Clientes y Productos son opcionales.")
        up_v = st.file_uploader("Ventas (.xlsx / .csv)", type=["xlsx", "xls", "csv"], key="up_v")
        up_c = st.file_uploader("Clientes (opcional)", type=["xlsx", "xls", "csv"], key="up_c")
        up_p = st.file_uploader("Productos (opcional)", type=["xlsx", "xls", "csv"], key="up_p")
        if up_v or up_c or up_p:
            st.success("Usando archivos cargados en esta sesión.")

vb, vn = pick(up_v, "ventas")
pb, pn = pick(up_p, "productos")
cb, cn = pick(up_c, "clientes")
if vb is None:
    st.error("No hay base de ventas. Cargue un archivo desde la barra lateral.")
    st.stop()
try:
    DF, WARNINGS, ERRORS = load_all(vb, vn, pb, pn, cb, cn)
except Exception as e:  # lectura fallida
    st.error(f"No se pudo leer el archivo de ventas: {e}")
    st.stop()
if ERRORS:
    for e in ERRORS:
        st.error(e)
    st.stop()

# ----------------------------------------------------------------------------- filtros
with st.sidebar:
    st.markdown("### 🔎 Filtros")
    dmin, dmax = DF["Fecha"].min().date(), DF["Fecha"].max().date()
    rng = st.date_input("Fecha", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    ciudades = st.multiselect("Ciudad", sorted(DF["Ciudad"].dropna().unique()), placeholder="Todas")
    base_s = DF if not ciudades else DF[DF["Ciudad"].isin(ciudades)]
    sucursales = st.multiselect("Sucursal", sorted(base_s["Sucursal"].dropna().unique()), placeholder="Todas")
    segmentos = st.multiselect("Segmento de cliente", sorted(DF["Segmento"].dropna().unique()), placeholder="Todos")
    cats = st.multiselect("Categoría", sorted(DF["Categoria"].dropna().unique()), placeholder="Todas")
    base_p = DF if not cats else DF[DF["Categoria"].isin(cats)]
    productos = st.multiselect("Producto", sorted(base_p["Producto"].dropna().unique()), placeholder="Todos")
    canales = st.multiselect("Canal", sorted(DF["Canal"].dropna().unique()), placeholder="Todos")

f = DF.copy()
if isinstance(rng, (list, tuple)) and len(rng) == 2:
    f = f[(f["Fecha"].dt.date >= rng[0]) & (f["Fecha"].dt.date <= rng[1])]
for col, sel in [("Ciudad", ciudades), ("Sucursal", sucursales), ("Segmento", segmentos), ("Categoria", cats),
                 ("Producto", productos), ("Canal", canales)]:
    if sel:
        f = f[f[col].isin(sel)]
FILTROS = {"fecha": [str(x) for x in rng] if isinstance(rng, (list, tuple)) else str(rng), "ciudad": ciudades or "todas",
           "sucursal": sucursales or "todas", "segmento": segmentos or "todos", "categoria": cats or "todas",
           "producto": productos or "todos", "canal": canales or "todos"}

st.title("🍕 San Francisco Crust Pizza · Dashboard ejecutivo")
st.caption(f"Datos: **{vn}** · {len(DF):,} registros de venta · {DF['Fecha'].min():%d/%m/%Y} – {DF['Fecha'].max():%d/%m/%Y}")
if f.empty:
    st.warning("Los filtros seleccionados no devuelven datos. Ajuste los filtros.")
    st.stop()

K = kpis.kpis(f)
c = st.columns(6)
c[0].metric("Ventas totales", usd(K["ventas"]))
c[1].metric("Utilidad bruta", usd(K["utilidad"]))
c[2].metric("Margen bruto", pct(K["margen"]))
c[3].metric("Ticket promedio", f"${K['ticket']:.2f}")
c[4].metric("Clientes", f"{K['clientes']:,}")
c[5].metric("Transacciones", f"{K['transacciones']:,}")
Y = kpis.yoy_table(f)
if Y:
    st.caption(f"**Variación {Y['y1']} vs {Y['y0']}** (dentro de los filtros): "
               f"ventas **{Y['ventas']*100:+.1f}%** · utilidad **{Y['utilidad']*100:+.1f}%** · transacciones **{Y['transacciones']*100:+.1f}%** · "
               f"ticket **{Y['ticket']*100:+.1f}%** · margen **{Y['margen_pts']:+.1f} pts** · clientes con compra **{Y['clientes']*100:+.1f}%**")

tabs = st.tabs(["📊 Ejecutivo", "🍕 Productos", "🏬 Sucursales y ciudades", "💸 Descuentos y servicio", "👥 Clientes", "🤖 Asistente IA", "🗂️ Datos"])

# ----------------------------------------------------------------------------- 1. Ejecutivo
with tabs[0]:
    st.plotly_chart(charts.line_monthly(kpis.monthly(f)), width="stretch")
    a, b = st.columns(2)
    prod = kpis.product_table(f)
    a.plotly_chart(charts.bar_h(prod, "Ventas", "Producto", "Top 10 productos más vendidos (USD)"), width="stretch")
    ciu = kpis.group_kpis(f, "Ciudad")
    b.plotly_chart(charts.bar_v(ciu, "Ciudad", "Ventas", "Ventas por ciudad (USD)"), width="stretch")
    a, b = st.columns(2)
    br = kpis.branch_ranking(f)
    a.plotly_chart(charts.branch_bars(br), width="stretch")
    seg = kpis.group_kpis(f, "Segmento")
    b.plotly_chart(charts.donut(seg, "Segmento", "Ventas", "Ventas por segmento de cliente"), width="stretch")
    a, b = st.columns(2)
    cat = kpis.group_kpis(f, "Categoria")
    a.plotly_chart(charts.donut(cat, "Categoria", "Ventas", "Ventas por categoría"), width="stretch")
    can = kpis.group_kpis(f, "Canal")
    b.plotly_chart(charts.bar_v(can, "Canal", "Ventas", "Ventas por canal (USD)"), width="stretch")
    ye = kpis.yoy_by(f, "Ciudad")
    if not ye.empty:
        st.markdown("**Variación anual de ventas por ciudad**")
        cfg = {c_: st.column_config.NumberColumn(format="$%.0f") for c_ in ye.columns if c_ not in ("Ciudad", "Variación")}
        cfg["Variación"] = st.column_config.NumberColumn(format="percent")
        st.dataframe(ye, hide_index=True, width="stretch", column_config=cfg)

# ----------------------------------------------------------------------------- 2. Productos
with tabs[1]:
    pt = kpis.product_table(f)
    st.plotly_chart(charts.pareto(pt), width="stretch")
    n80 = int((pt["%Acum"] < 0.8).sum() + 1)
    st.caption(f"{n80} de {len(pt)} productos ({n80/len(pt):.0%}) concentran el 80% de las ventas.")
    st.plotly_chart(charts.product_scatter(pt), width="stretch")
    a, b = st.columns(2)
    a.plotly_chart(charts.bar_h(pt.rename(columns={"Utilidad": "U"}), "U", "Producto", "Top 10 por utilidad bruta (USD)", color=charts.GREEN), width="stretch")
    low = pt.sort_values("Margen").head(10).sort_values("Margen", ascending=False)
    a2 = charts.bar_h(low.assign(M=low["Margen"]), "M", "Producto", "10 productos con menor margen bruto", color=charts.ORANGE, fmt="%")
    b.plotly_chart(a2, width="stretch")
    st.markdown("**Matriz de decisión por producto**")
    show = pt[["Producto", "Categoria", "Ventas", "Utilidad", "Margen", "%Ventas", "Decisión"]]
    st.dataframe(show, hide_index=True, width="stretch", column_config={
        "Ventas": st.column_config.NumberColumn(format="$%.0f"), "Utilidad": st.column_config.NumberColumn(format="$%.0f"),
        "Margen": st.column_config.NumberColumn(format="percent"), "%Ventas": st.column_config.NumberColumn(format="percent")})
    gap = kpis.catalog_gap(f)
    if not gap.empty:
        st.markdown("**Margen del catálogo vs. margen realizado en ventas** (pts porcentuales)")
        st.dataframe(gap.round(1), hide_index=True, width="stretch", column_config={
            "Ventas": st.column_config.NumberColumn(format="$%.0f"), "Utilidad": st.column_config.NumberColumn(format="$%.0f"),
            "MargenCat": st.column_config.NumberColumn("Margen catálogo %", format="%.1f"),
            "MargenReal": st.column_config.NumberColumn("Margen real %", format="%.1f")})
    inact = f[f["Activo"].astype(str).str.lower().isin(["no", "false", "0"])]
    if len(inact):
        st.warning(f"⚠️ {usd(inact['VentaNeta'].sum())} ({inact['VentaNeta'].sum()/K['ventas']:.1%} de las ventas) corresponden a productos marcados como **inactivos** en el catálogo: "
                   + ", ".join(sorted(inact['ProductoTam'].unique())))

# ----------------------------------------------------------------------------- 3. Sucursales
with tabs[2]:
    br = kpis.branch_ranking(f)
    a, b = st.columns([1, 1])
    a.plotly_chart(charts.score_bars(br), width="stretch")
    best, worst = br.iloc[0], br.iloc[-1]
    b.success(f"🏆 **Mejor desempeño:** {best['Sucursal']} · ventas {usd(best['Ventas'])} · margen {pct(best['Margen'])} · ticket ${best['Ticket']:.2f}")
    b.error(f"⚠️ **Menor desempeño:** {worst['Sucursal']} · ventas {usd(worst['Ventas'])} · margen {pct(worst['Margen'])} · ticket ${worst['Ticket']:.2f}")
    b.caption("Score = 35% ventas + 25% utilidad + 20% margen + 20% ticket (cada indicador normalizado 0–1 entre sucursales).")
    cols = [c_ for c_ in ["Ranking", "Sucursal", "Ciudad", "Ventas", "Utilidad", "Margen", "Ticket", "Transacciones", "Clientes", "VarAnual", "Score"] if c_ in br.columns]
    st.dataframe(br[cols], hide_index=True, width="stretch", column_config={
        "Ventas": st.column_config.NumberColumn(format="$%.0f"), "Utilidad": st.column_config.NumberColumn(format="$%.0f"),
        "Margen": st.column_config.NumberColumn(format="percent"), "Ticket": st.column_config.NumberColumn(format="$%.2f"),
        "VarAnual": st.column_config.NumberColumn("Var. anual ventas", format="percent"), "Score": st.column_config.NumberColumn(format="%.1f")})
    st.plotly_chart(charts.line_monthly(kpis.monthly(f, "Ciudad"), color="Ciudad", title="Ventas mensuales por ciudad (USD)"), width="stretch")
    st.plotly_chart(charts.heat(f, "Sucursal", "Periodo", "VentaNeta", "Mapa de calor: ventas por sucursal y mes (USD)"), width="stretch")

# ----------------------------------------------------------------------------- 4. Descuentos y servicio
with tabs[3]:
    dt = kpis.discount_table(f)
    a, b = st.columns(2)
    a.plotly_chart(charts.discount_margin(dt), width="stretch")
    dc = kpis.discount_by(f, "Ciudad")
    b.plotly_chart(charts.bar_v(dc.assign(x=dc["DescMedio"]), "Ciudad", "x", "Descuento medio por ciudad (%)", fmt="%", h=340).update_traces(texttemplate="%{y:.1f}%"), width="stretch")
    mm = f.groupby(["Periodo", "Ciudad"]).agg(Descuento=("DescuentoPct", "mean")).reset_index()
    import plotly.express as px
    fig = px.line(mm, x="Periodo", y="Descuento", color="Ciudad", markers=True)
    fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(charts._fmt(fig, "Descuento medio mensual por ciudad (%)"), width="stretch")
    st.dataframe(dc.rename(columns={"ConDescuento": "% trans. con descuento", "DescMedio": "Desc. medio %", "DescUSD": "Descuento USD"}),
                 hide_index=True, width="stretch", column_config={
        "% trans. con descuento": st.column_config.NumberColumn(format="percent"), "Desc. medio %": st.column_config.NumberColumn(format="%.2f"),
        "Descuento USD": st.column_config.NumberColumn(format="$%.0f"), "Ventas": st.column_config.NumberColumn(format="$%.0f"),
        "Utilidad": st.column_config.NumberColumn(format="$%.0f"), "Margen": st.column_config.NumberColumn(format="percent")})
    dl = f[f["Canal"].astype(str).str.lower().eq("delivery") & f["TiempoEntregaMin"].notna()]
    if len(dl):
        st.markdown("#### Tiempo de entrega (canal Delivery)")
        a, b = st.columns(2)
        d1 = kpis.delivery_by(f, "Sucursal")
        a.plotly_chart(charts._fmt(px.bar(d1.sort_values("EntregaMin"), x="EntregaMin", y="Sucursal", orientation="h", color_discrete_sequence=[charts.ORANGE],
                                       text=d1.sort_values("EntregaMin")["EntregaMin"].map(lambda v: f"{v:.0f} min")), "Minutos promedio de entrega por sucursal").update_xaxes(visible=False), width="stretch")
        d2 = dl.groupby(["Periodo", "Ciudad"]).agg(Min=("TiempoEntregaMin", "mean")).reset_index()
        fg = px.line(d2, x="Periodo", y="Min", color="Ciudad", markers=True)
        b.plotly_chart(charts._fmt(fg, "Minutos promedio de entrega por mes y ciudad"), width="stretch")

# ----------------------------------------------------------------------------- 5. Clientes
with tabs[4]:
    cv = kpis.customer_view(f)
    if "ClienteActivo" not in cv.columns:
        st.info("La base de clientes no está disponible: cárguela desde la barra lateral para ver el análisis CRM.")
    else:
        act = cv["ClienteActivo"].astype(str).str.lower().isin(["sí", "si", "yes", "true", "1"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Clientes en el filtro", f"{len(cv):,}")
        c2.metric("Clientes activos", pct(act.mean()))
        c3.metric("NPS promedio (0–10)", f"{cv['NPS'].mean():.1f}" if "NPS" in cv else "n/d")
        c4.metric("Gasto acumulado medio", usd(cv["GastoAcumuladoUSD"].mean()) if "GastoAcumuladoUSD" in cv else "n/d")
        sc = kpis.segment_crm(f)
        a, b = st.columns(2)
        sg = kpis.group_kpis(f, "Segmento")
        mix = sg[["Segmento", "%Ventas"]].merge(sc[["Segmento", "%Clientes"]], on="Segmento").melt("Segmento", var_name="Métrica", value_name="Participación")
        import plotly.express as px
        a.plotly_chart(charts._fmt(px.bar(mix, x="Segmento", y="Participación", color="Métrica", barmode="group", color_discrete_sequence=[charts.RED, charts.YELLOW],
                                          text=mix["Participación"].map(lambda v: f"{v:.1%}")), "Participación en ventas vs. en clientes").update_yaxes(visible=False), width="stretch")
        cr = kpis.churn_reasons(f)
        if not cr.empty:
            b.plotly_chart(charts.bar_h(cr.rename(columns={"Clientes": "N"}), "N", "MotivoPerdida", "Motivos de pérdida de clientes inactivos (n)", color=charts.ORANGE, fmt="n").update_traces(texttemplate="%{x}"), width="stretch")
        st.markdown("**Perfil CRM por segmento**")
        st.dataframe(sc, hide_index=True, width="stretch", column_config={
            "Activos": st.column_config.NumberColumn("% activos", format="percent"), "NPS": st.column_config.NumberColumn(format="%.1f"),
            "GastoProm": st.column_config.NumberColumn("Gasto acumulado medio", format="$%.0f"), "TicketCRM": st.column_config.NumberColumn("Ticket CRM", format="$%.0f"),
            "%Clientes": st.column_config.NumberColumn(format="percent")})
        if "MotivoPerdida" in cv.columns:
            ct = pd.crosstab(cv["Segmento"], cv["MotivoPerdida"].replace("", np.nan).dropna())
            st.markdown("**Motivo de pérdida por segmento (n clientes)**")
            st.dataframe(ct, width="stretch")
        st.caption("Nota: los atributos CRM (activo, NPS, gasto acumulado) provienen de la base de Clientes; las ventas, de la base de Ventas.")

# ----------------------------------------------------------------------------- 6. Asistente IA
with tabs[5]:
    st.subheader("🤖 Asistente de IA para recomendaciones comerciales")
    st.caption("El asistente recibe los indicadores del dashboard **con los filtros activos** y redacta recomendaciones. "
               "Toda recomendación debe ser validada críticamente por el equipo antes de incorporarla a las conclusiones.")
    try:
        secrets = st.secrets
    except Exception:
        secrets = None
    with st.expander("⚙️ Proveedor de IA (API compatible con OpenAI)"):
        key_in = st.text_input("API key (solo para esta sesión)", type="password", help="Alternativa: definir OPENAI_API_KEY en los Secrets de Streamlit Cloud.")
        base_in = st.text_input("Base URL", value=ai.get_config(secrets)["base_url"])
        model_in = st.text_input("Modelo", value=ai.get_config(secrets)["model"])
    cfg = ai.get_config(secrets, key_in or None)
    cfg["base_url"], cfg["model"] = base_in.rstrip("/"), model_in
    CTX = kpis.build_context(f, FILTROS)
    has_llm = bool(cfg["api_key"])
    st.info(("🟢 Modo **LLM**: " + cfg["model"]) if has_llm else "🟡 Sin API key: se usará el **motor de reglas** de respaldo (determinista). Configure una API key para activar el LLM.")

    if "chat" not in st.session_state:
        st.session_state.chat = []
    col_a, col_b = st.columns([1, 1])
    gen = col_a.button("✨ Generar recomendaciones", type="primary", width="stretch")
    if col_b.button("🧹 Limpiar conversación", width="stretch"):
        st.session_state.chat = []
    question = st.chat_input("Pregunte al asistente sobre los datos filtrados…")
    prompt = ai.DEFAULT_REQUEST if gen else question
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt if question else "Generar recomendaciones comerciales con los datos filtrados."})
        with st.spinner("Analizando…"):
            try:
                if has_llm:
                    ans = ai.ask_llm(cfg, prompt, CTX, st.session_state.chat[:-1])
                else:
                    ans = kpis.rule_based_recs(CTX) if gen else ("Para responder preguntas libres se necesita una API key de LLM. "
                                                                 "Mientras tanto, pulse **Generar recomendaciones** (motor de reglas).")
            except Exception as e:
                ans = f"⚠️ No se pudo consultar el proveedor de IA: {e}\n\n" + kpis.rule_based_recs(CTX)
        st.session_state.chat.append({"role": "assistant", "content": ans})
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    with st.expander("🔍 Contexto (JSON) enviado al asistente — transparencia y trazabilidad"):
        st.json(CTX, expanded=False)

# ----------------------------------------------------------------------------- 7. Datos
with tabs[6]:
    st.subheader("Calidad y trazabilidad de los datos")
    st.write(f"**Ventas:** {vn} · **Productos:** {pn or '—'} · **Clientes:** {cn or '—'}")
    if WARNINGS:
        for w in WARNINGS:
            st.warning(w)
    else:
        st.success("Sin avisos de calidad de datos.")
    st.markdown("**Esquema mínimo de Ventas:** Fecha, ClienteID, ProductoID, Cantidad, Sucursal. Opcionales: Ciudad, PrecioUnitario, CostoUnitario, DescuentoPct, "
                "VentaNeta, CostoTotal, UtilidadBruta, Canal, FormaPago, TiempoEntregaMin. Si faltan VentaNeta/CostoTotal se calculan.")
    st.dataframe(f.head(200), width="stretch", hide_index=True)
    st.download_button("⬇️ Descargar datos filtrados (CSV)", f.to_csv(index=False).encode("utf-8-sig"), "ventas_filtradas.csv", "text/csv")
