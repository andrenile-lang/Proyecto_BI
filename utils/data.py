"""Carga, validación y enriquecimiento de datos (ETL ligero).

La app NO depende de nombres de archivo ni de valores fijos: lee cualquier base de
ventas (xlsx/csv) que respete el esquema mínimo y recalcula todo automáticamente.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# columna canónica -> alias normalizados aceptados
ALIASES = {
    "VentaID": ["ventaid", "idventa", "transaccion", "transaccionid", "ticketid", "facturaid", "pedidoid"],
    "Fecha": ["fecha", "fechaventa", "fechadeventa", "fechadelaventa", "fechatransaccion", "date", "fechapedido"],
    "Ciudad": ["ciudad", "city"],
    "Sucursal": ["sucursal", "tienda", "local", "branch", "store"],
    "ClienteID": ["clienteid", "idcliente", "cliente", "customerid"],
    "ProductoID": ["productoid", "idproducto", "producto", "sku", "productid"],
    "Cantidad": ["cantidad", "unidades", "qty", "quantity"],
    "PrecioUnitario": ["preciounitario", "precio", "preciounit", "unitprice"],
    "CostoUnitario": ["costounitario", "costounit", "unitcost"],
    "DescuentoPct": ["descuentopct", "descuento", "descuentoporcentaje", "discount"],
    "VentaNeta": ["ventaneta", "ventas", "venta", "ventatotal", "importe", "ingreso", "total", "monto"],
    "CostoTotal": ["costototal", "costo", "costos", "totalcosto"],
    "UtilidadBruta": ["utilidadbruta", "utilidad", "margenbruto", "gananciabruta"],
    "Canal": ["canal", "channel", "tipopedido"],
    "FormaPago": ["formapago", "metodopago", "pago"],
    "TiempoEntregaMin": ["tiempoentregamin", "tiempoentrega", "entregamin", "deliverytime"],
    "TiempoPreparacionMin": ["tiempopreparacionmin", "tiempopreparacion", "preparacionmin"],
}
ALIASES_PROD = {
    "ProductoID": ["productoid", "idproducto", "sku"],
    "Categoria": ["categoria", "category", "familia"],
    "Producto": ["producto", "nombre", "nombreproducto", "product"],
    "Tamaño": ["tamano", "tamaño", "size"],
    "CostoUSD": ["costousd", "costo", "costounitario"],
    "PrecioVentaUSD": ["precioventausd", "precioventa", "precio", "preciounitario"],
    "MargenPorcentaje": ["margenporcentaje", "margenpct", "margen"],
    "Activo": ["activo", "active", "vigente"],
}
ALIASES_CLI = {
    "ClienteID": ["clienteid", "idcliente", "cliente"],
    "Nombre": ["nombre", "name"],
    "Ciudad": ["ciudad", "city"],
    "Segmento": ["segmento", "segment"],
    "TotalCompras": ["totalcompras"],
    "GastoAcumuladoUSD": ["gastoacumuladousd", "gastoacumulado"],
    "TicketPromedioUSD": ["ticketpromediousd", "ticketpromedio"],
    "ClienteActivo": ["clienteactivo", "activo"],
    "NPS": ["nps"],
    "MotivoPerdida": ["motivoperdida", "motivodeperdida"],
    "CanalFavorito": ["canalfavorito"],
}
REQUIRED_VENTAS = ["Fecha", "ClienteID", "ProductoID", "Cantidad", "Sucursal"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _rename(df: pd.DataFrame, aliases: dict) -> pd.DataFrame:
    lookup = {}
    for canon, alts in aliases.items():
        lookup[_norm(canon)] = canon
        for a in alts:
            lookup.setdefault(a, canon)
    new, used = {}, set()
    for col in df.columns:
        canon = lookup.get(_norm(col))
        if canon and canon not in used:
            new[col] = canon
            used.add(canon)
    return df.rename(columns=new)


def read_any(source, name: str | None = None) -> pd.DataFrame:
    """Lee xlsx/xls/csv desde ruta o bytes."""
    if isinstance(source, (bytes, bytearray)):
        buf, name = io.BytesIO(source), (name or "archivo.xlsx")
    else:
        buf, name = source, (name or str(source))
    if name.lower().endswith((".csv", ".txt")):
        return pd.read_csv(buf, sep=None, engine="python", encoding_errors="replace")
    return pd.read_excel(buf)


def file_signature(path: Path) -> str:
    """Firma por tamaño+fecha: si se reemplaza el archivo en /data, se invalida la caché."""
    if not path.exists():
        return "none"
    st = path.stat()
    return f"{path.name}-{st.st_size}-{int(st.st_mtime)}"


def find_default(kind: str) -> Path | None:
    for p in sorted(DATA_DIR.glob("*")):
        if p.suffix.lower() in (".xlsx", ".xls", ".csv") and kind.lower() in p.name.lower():
            return p
    return None


def build_dataset(ventas_raw, productos_raw=None, clientes_raw=None):
    """Devuelve (df_enriquecido, clientes_df, productos_df, avisos, errores)."""
    warnings, errors = [], []
    v = _rename(ventas_raw.copy(), ALIASES)
    missing = [c for c in REQUIRED_VENTAS if c not in v.columns]
    if missing:
        return None, None, None, warnings, [
            "La base de ventas no contiene las columnas mínimas requeridas: " + ", ".join(missing)
            + ". Columnas recibidas: " + ", ".join(map(str, ventas_raw.columns))
        ]

    v["Fecha"] = pd.to_datetime(v["Fecha"], errors="coerce")
    bad = int(v["Fecha"].isna().sum())
    if bad:
        warnings.append(f"{bad:,} filas con fecha inválida fueron excluidas.")
        v = v.dropna(subset=["Fecha"])
    for c in ["Cantidad", "PrecioUnitario", "CostoUnitario", "DescuentoPct", "VentaNeta", "CostoTotal",
              "UtilidadBruta", "TiempoEntregaMin", "TiempoPreparacionMin"]:
        if c in v.columns:
            v[c] = pd.to_numeric(v[c], errors="coerce")
    if "VentaID" not in v.columns:
        v["VentaID"] = np.arange(1, len(v) + 1).astype(str)
        warnings.append("No existe columna de ID de venta; se generó un ID por fila.")
    if "Ciudad" not in v.columns:
        v["Ciudad"] = "Sin ciudad"
    for c, default in [("Canal", "N/D"), ("FormaPago", "N/D")]:
        if c not in v.columns:
            v[c] = default
    v["DescuentoPct"] = v["DescuentoPct"].fillna(0) if "DescuentoPct" in v.columns else 0.0
    v["Cantidad"] = v["Cantidad"].fillna(1)

    # ---- productos
    prod = None
    if productos_raw is not None:
        prod = _rename(productos_raw.copy(), ALIASES_PROD)
        if "ProductoID" not in prod.columns:
            warnings.append("La base de productos no tiene ProductoID; se ignoró.")
            prod = None
    if prod is not None:
        for c, default in [("Categoria", "Sin categoría"), ("Producto", None), ("Tamaño", ""), ("Activo", "Sí")]:
            if c not in prod.columns:
                prod[c] = prod["ProductoID"] if (c == "Producto") else default
        prod = prod.drop_duplicates("ProductoID")
        keep = [c for c in ["ProductoID", "Categoria", "Producto", "Tamaño", "Activo", "CostoUSD",
                            "PrecioVentaUSD", "MargenPorcentaje"] if c in prod.columns]
        v = v.merge(prod[keep], on="ProductoID", how="left")
        nomatch = int(v["Producto"].isna().sum())
        if nomatch:
            warnings.append(f"{nomatch:,} ventas con ProductoID que no existe en Productos.")
        v["Producto"] = v["Producto"].fillna(v["ProductoID"])
        v["Categoria"] = v["Categoria"].fillna("Sin categoría")
        v["Tamaño"] = v["Tamaño"].fillna("")
        v["Activo"] = v["Activo"].fillna("N/D")
    else:
        v["Producto"], v["Categoria"], v["Tamaño"], v["Activo"] = v["ProductoID"], "Sin categoría", "", "N/D"
    v["ProductoTam"] = (v["Producto"].astype(str) + " " + v["Tamaño"].astype(str)).str.strip()

    # ---- cálculos monetarios (se respetan los valores de la base si existen)
    if "VentaNeta" not in v.columns:
        price = v["PrecioUnitario"] if "PrecioUnitario" in v.columns else v.get("PrecioVentaUSD")
        if price is None:
            return None, None, None, warnings, ["No hay VentaNeta ni precio (PrecioUnitario/Productos) para calcular ventas."]
        v["VentaNeta"] = (v["Cantidad"] * price * (1 - v["DescuentoPct"] / 100)).round(2)
        warnings.append("VentaNeta se calculó como Cantidad × Precio × (1 − Descuento).")
    if "CostoTotal" not in v.columns:
        cost = v["CostoUnitario"] if "CostoUnitario" in v.columns else v.get("CostoUSD")
        if cost is None:
            return None, None, None, warnings, ["No hay CostoTotal ni costo unitario para calcular utilidad."]
        v["CostoTotal"] = (v["Cantidad"] * cost).round(2)
        warnings.append("CostoTotal se calculó como Cantidad × Costo unitario.")
    if "UtilidadBruta" not in v.columns:
        v["UtilidadBruta"] = (v["VentaNeta"] - v["CostoTotal"]).round(2)
    if "PrecioUnitario" in v.columns:
        v["DescuentoUSD"] = (v["Cantidad"] * v["PrecioUnitario"] - v["VentaNeta"]).clip(lower=0)
    else:
        v["DescuentoUSD"] = 0.0
    for c in ["TiempoEntregaMin", "TiempoPreparacionMin"]:
        if c not in v.columns:
            v[c] = np.nan

    # ---- clientes
    cli = None
    if clientes_raw is not None:
        cli = _rename(clientes_raw.copy(), ALIASES_CLI)
        if "ClienteID" not in cli.columns:
            warnings.append("La base de clientes no tiene ClienteID; se ignoró.")
            cli = None
    if cli is not None:
        cli = cli.drop_duplicates("ClienteID")
        if "Segmento" not in cli.columns:
            cli["Segmento"] = "Sin segmento"
        ren = {"Ciudad": "CiudadCliente"}
        v = v.merge(cli.rename(columns=ren)[[c for c in ["ClienteID", "Segmento", "CiudadCliente", "ClienteActivo",
                                                          "NPS", "MotivoPerdida", "GastoAcumuladoUSD",
                                                          "TicketPromedioUSD", "TotalCompras"] if c in cli.rename(columns=ren).columns]],
                    on="ClienteID", how="left")
        nomatch = int(v["Segmento"].isna().sum())
        if nomatch:
            warnings.append(f"{nomatch:,} ventas con ClienteID que no existe en Clientes (segmento = 'Sin segmento').")
        v["Segmento"] = v["Segmento"].fillna("Sin segmento")
    else:
        v["Segmento"] = "Sin segmento"

    dup = int(v["VentaID"].duplicated().sum())
    if dup:
        warnings.append(f"{dup:,} filas repiten VentaID (se interpretan como varias líneas de una misma transacción).")
    if prod is not None and "Activo" in prod.columns:
        inact = v[v["Activo"].astype(str).str.lower().isin(["no", "false", "0"])]
        if len(inact):
            warnings.append(f"{inact['VentaNeta'].sum():,.0f} USD de ventas corresponden a productos marcados como inactivos en el catálogo.")

    v["Año"] = v["Fecha"].dt.year
    v["Mes"] = v["Fecha"].dt.month
    v["Periodo"] = v["Fecha"].dt.to_period("M").dt.to_timestamp()
    v["Trimestre"] = v["Fecha"].dt.quarter
    return v, cli, prod, warnings, errors
