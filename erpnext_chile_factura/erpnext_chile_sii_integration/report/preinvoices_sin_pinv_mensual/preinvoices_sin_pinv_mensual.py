import frappe
import io
import zipfile
from frappe.utils.file_manager import get_file, get_file_path
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
        {
            "label": "XML",
            "fieldname": "xml_link",
            "fieldtype": "Data",
            "width": 150
        },
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
            pi.monto_total,
            f.file_url AS xml_link
        FROM `tabPreInvoice` pi
        LEFT JOIN `tabPurchase Invoice` pinv
            ON pinv.bill_no = CAST(pi.folio AS CHAR)
            AND pinv.rut = pi.rut_proveedor
            AND pinv.tipo_dte = pi.tipo_dte
            AND pinv.docstatus = 1
        LEFT JOIN `tabFile` f
            ON f.attached_to_doctype = 'PreInvoice'
            AND f.attached_to_name = pi.name
            AND f.file_name LIKE '%%.xml'
        WHERE pi.estado = 'Confirmada'
          AND pi.mes_libro_sii BETWEEN %(inicio)s AND %(fin)s
          AND pinv.name IS NULL
        ORDER BY pi.fecha_emision DESC
    """

    data = frappe.db.sql(sql, {"inicio": inicio, "fin": fin}, as_dict=True)

    # Opcional: formatear como link clickeable
    for row in data:
        if row.get("xml_link"):
            row["xml_link"] = f'<a href="{row["xml_link"]}" target="_blank">Descargar XML</a>'

    return columns, data


@frappe.whitelist()
def download_xml_zip(filters):
    """Encola la generación del ZIP y notifica al usuario por email."""
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    user = frappe.session.user  # usuario que ejecutó
    frappe.enqueue(
        "erpnext_chile_factura.erpnext_chile_sii_integration.report.preinvoices_sin_pinv_mensual.preinvoices_sin_pinv_mensual._generate_zip_and_mail",
        filters=filters,
        user=user,
        queue="long",
        timeout=600
    )
    return "El ZIP se está generando. Recibirás un correo cuando esté listo."

def _generate_zip_and_mail(filters, user):
    mes = filters.get("mes_libro_sii")
    if not mes:
        return

    inicio = get_first_day(mes)
    fin = get_last_day(mes)

    preinvoices = frappe.get_all(
        "PreInvoice",
        filters={"estado": "Confirmada", "mes_libro_sii": ["between", [inicio, fin]]},
        fields=["name"]
    )
    if not preinvoices:
        frappe.sendmail(
            recipients=user,
            subject="ZIP XML PreInvoices",
            message="No se encontraron PreInvoices con XML en este período."
        )
        return

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for pre in preinvoices:
            files = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "PreInvoice",
                    "attached_to_name": pre.name,
                    "file_name": ["like", "%.xml"]
                },
                fields=["file_url", "file_name"]
            )
            for f in files:
                content, _ = get_file(f.file_url)  # obtiene el binario directo
                zf.writestr(f.file_name, content)

    mem_zip.seek(0)

    # ✉️ enviar por correo como adjunto (sin guardarlo en File Manager)
    frappe.sendmail(
        recipients=user,
        subject=f"ZIP de XML PreInvoices {mes}",
        message="Adjunto encontrarás el archivo ZIP con los XML de las PreInvoices.",
        attachments=[{
            "fname": f"xml_preinvoices_{mes}.zip",
            "fcontent": mem_zip.getvalue()
        }]
    )