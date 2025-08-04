import frappe
from frappe.utils import get_first_day, get_last_day

TIPOS_DTE = {
    33: "Factura Electrónica",
    34: "Factura Exenta",
    46: "Factura de Compra",
    56: "Nota de Débito",
    61: "Nota de Crédito",
}

import frappe
from frappe.utils import get_first_day, get_last_day

TIPOS_DTE = {
    33: "Factura Electrónica",
    34: "Factura Exenta",
    46: "Factura de Compra",
    56: "Nota de Débito",
    61: "Nota de Crédito",
}

def execute(filters=None):
    if not filters or not filters.get("mes_libro_sii"):
        frappe.throw("Debes seleccionar el Mes del Libro SII.")

    mes = filters["mes_libro_sii"]
    inicio = get_first_day(mes)
    fin = get_last_day(mes)

    columns = [
		{
			"label": "PreInvoice",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "PreInvoice",
			"width": 140
		},
		{"label": "Tipo DTE", "fieldname": "tipo_dte", "fieldtype": "Data", "width": 140},
		{"label": "Folio", "fieldname": "folio", "fieldtype": "Int", "width": 80},
		{"label": "RUT Proveedor", "fieldname": "rut_proveedor", "fieldtype": "Data", "width": 120},
		{"label": "Razón Social", "fieldname": "razon_social", "fieldtype": "Data", "width": 200},
		{"label": "Fecha Emisión", "fieldname": "fecha_emision", "fieldtype": "Date", "width": 100},
		{"label": "Monto Neto", "fieldname": "monto_neto", "fieldtype": "Currency", "width": 120, "precision": 0},
		{"label": "IVA", "fieldname": "monto_iva_recuperable", "fieldtype": "Currency", "width": 100, "precision": 0},
		{"label": "Total", "fieldname": "monto_total", "fieldtype": "Currency", "width": 120, "precision": 0},
	]


    sql = """
        SELECT
			pi.name,
            CASE
                WHEN pi.tipo_dte = 33 THEN 'Factura Electrónica'
                WHEN pi.tipo_dte = 34 THEN 'Factura Exenta'
                WHEN pi.tipo_dte = 46 THEN 'Factura de Compra'
                WHEN pi.tipo_dte = 56 THEN 'Nota de Débito'
                WHEN pi.tipo_dte = 61 THEN 'Nota de Crédito'
                ELSE CONCAT('DTE ', pi.tipo_dte)
            END AS tipo_dte,
            pi.folio,
            pi.rut_proveedor,
            pi.razon_social,
            pi.fecha_emision,
            pi.monto_neto,
            pi.monto_iva_recuperable,
            pi.monto_total
        FROM `tabPreInvoice` pi
        LEFT JOIN `tabPurchase Invoice` pinv
            ON pinv.bill_no = CAST(pi.folio AS CHAR)
            AND pinv.rut = pi.rut_proveedor
            AND pinv.tipo_dte = pi.tipo_dte
            AND pinv.docstatus = 1
        WHERE pi.estado = 'Confirmada'
          AND pi.mes_libro_sii BETWEEN %(inicio)s AND %(fin)s
          AND pinv.name IS NULL
        ORDER BY pi.fecha_emision DESC
    """

    data = frappe.db.sql(sql, {"inicio": inicio, "fin": fin}, as_dict=True)

    return columns, data
