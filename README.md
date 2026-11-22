# 🍕 SF Crust Pizza · Sistema Inteligente de Apoyo a la Toma de Decisiones

Dashboard web interactivo (Streamlit + Pandas + Plotly) con asistente de IA para San Francisco Crust Pizza.

## Estructura
```
SF_PIZZA_BI/
├── app.py                 # Aplicación (UI, filtros, pestañas)
├── utils/
│   ├── data.py            # ETL: lectura xlsx/csv, validación, enriquecimiento (Ventas+Clientes+Productos)
│   ├── kpis.py            # KPIs, ranking de sucursales, Pareto, descuentos, CRM, contexto para IA
│   ├── charts.py          # Gráficos Plotly
│   └── ai.py              # Asistente IA (API compatible con OpenAI) + prompt de sistema
├── data/                  # Bases por defecto (Ventas, Clientes, Productos)
├── .streamlit/            # Tema y plantilla de secrets
└── requirements.txt
```

## Ejecutar en local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar con enlace público (Streamlit Community Cloud, gratis)
1. Cree un repositorio **público** en GitHub y suba el contenido de esta carpeta (sin `.streamlit/secrets.toml`).
2. Entre a https://share.streamlit.io con su cuenta de GitHub → **Create app** → seleccione repo, rama y `app.py`.
3. En **Advanced settings → Secrets** pegue (opcional, activa el LLM):
   ```toml
   OPENAI_API_KEY = "sk-..."
   # OPENAI_MODEL = "gpt-4o-mini"
   ```
4. **Deploy**. La URL resultante (`https://<nombre>.streamlit.app`) es el enlace público a entregar. Verifique que abre sin pedir inicio de sesión (Settings → Sharing → *Public*).
5. Abra la app unos minutos antes de la evaluación (las apps inactivas se "duermen" y se reactivan con un clic).

## Actualización automática (sin tocar código)
- **Desde la interfaz:** barra lateral → *Actualizar bases de datos* → cargue la nueva base de Ventas (.xlsx/.csv). Todos los KPI, gráficos y el asistente se recalculan.
- **Desde el repositorio:** reemplace el archivo de `data/` (mismo tipo de base) y haga *commit*; la app lee el nuevo archivo.
- Esquema mínimo de Ventas: `Fecha, ClienteID, ProductoID, Cantidad, Sucursal`. Si faltan `VentaNeta/CostoTotal/UtilidadBruta` se calculan con precio/costo de la propia base o del catálogo de Productos. Se reconocen alias de columnas (p. ej. *Tienda*, *Unidades*, *Fecha de venta*).

## Asistente de IA
- Con `OPENAI_API_KEY` (o clave en la pestaña *Asistente IA*) usa un LLM compatible con la API de OpenAI (`OPENAI_BASE_URL` y `OPENAI_MODEL` opcionales). Recibe un JSON con los indicadores **filtrados** y un prompt de sistema que le obliga a usar solo esos datos.
- Sin clave: motor de reglas determinista (respaldo) para que la app siempre responda.
- El contexto exacto enviado a la IA es visible en la app (trazabilidad).

## Definiciones
- Ventas = `VentaNeta`; Utilidad bruta = `VentaNeta − CostoTotal`; Margen = Utilidad / Ventas; Ticket = Ventas / Transacciones (`VentaID` únicos).
- Score de sucursal = 35 % ventas + 25 % utilidad + 20 % margen + 20 % ticket (min-max entre sucursales).
