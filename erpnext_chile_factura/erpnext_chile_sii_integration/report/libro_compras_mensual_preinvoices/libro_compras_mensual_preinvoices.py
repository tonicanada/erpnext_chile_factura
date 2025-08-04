import frappe
from frappe.utils import get_first_day, get_last_day

TIPOS_DTE = {
    33: "Factura Electrónica",
    34: "Factura Exenta",
    46: "Factura de Compra",
    56: "Nota de Débito",
    61: "Nota de Crédito",
    # Agrega más si usas otros
}

def execute(filters=None):
    if not filters or not filters.get("mes_libro_sii"):
        frappe.throw("Debes seleccionar el Mes del Libro SII.")

    mes = filters["mes_libro_sii"]
    inicio_mes = get_first_day(mes)
    fin_mes = get_last_day(mes)

    width = 130

    columns = [
        {"label": "Tipo DTE", "fieldname": "tipo_dte", "fieldtype": "Data", "width": 160},
        {"label": "Cantidad", "fieldname": "cantidad", "fieldtype": "Int", "width": 80},
        {"label": "Exento", "fieldname": "monto_exento", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "Neto", "fieldname": "monto_neto", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "IVA Recuperable", "fieldname": "monto_iva_recuperable", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "IVA No Recuperable", "fieldname": "monto_iva_no_recuperable", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "IVA Uso Común", "fieldname": "iva_uso_comun", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "IVA No Retenido", "fieldname": "iva_no_retenido", "fieldtype": "Currency", "width": width, "precision": 0},
        {"label": "Total", "fieldname": "monto_total", "fieldtype": "Currency", "width": width, "precision": 0},
    ]

    data = frappe.db.sql("""
        SELECT
            tipo_dte,
            COUNT(*) AS cantidad,
            SUM(monto_exento) AS monto_exento,
            SUM(monto_neto) AS monto_neto,
            SUM(monto_iva_recuperable) AS monto_iva_recuperable,
            SUM(monto_iva_no_recuperable) AS monto_iva_no_recuperable,
            SUM(iva_uso_comun) AS iva_uso_comun,
            SUM(iva_no_retenido) AS iva_no_retenido,
            SUM(monto_total) AS monto_total
        FROM `tabPreInvoice`
        WHERE mes_libro_sii BETWEEN %s AND %s
          AND estado = 'Confirmada'
        GROUP BY tipo_dte
        ORDER BY tipo_dte
    """, (inicio_mes, fin_mes), as_dict=True)

    total_row = {
        "tipo_dte": "TOTAL",
        "cantidad": 0,
        "monto_exento": 0,
        "monto_neto": 0,
        "monto_iva_recuperable": 0,
        "monto_iva_no_recuperable": 0,
        "iva_uso_comun": 0,
        "iva_no_retenido": 0,
        "monto_total": 0,
    }

    for row in data:
        tipo_dte_num = int(row["tipo_dte"])
        signo = -1 if tipo_dte_num == 61 else 1

        for key in [
            "monto_exento", "monto_neto", "monto_iva_recuperable",
            "monto_iva_no_recuperable", "iva_uso_comun", "iva_no_retenido", "monto_total"
        ]:
            row[key] = signo * (row.get(key, 0) or 0)

        row["tipo_dte"] = TIPOS_DTE.get(tipo_dte_num, f"DTE {tipo_dte_num}")

        for key in total_row:
            if key != "tipo_dte":
                total_row[key] += row.get(key, 0) or 0

    data.append(total_row)

    return columns, data
