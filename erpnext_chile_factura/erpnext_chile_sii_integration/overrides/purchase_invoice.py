import frappe

@frappe.whitelist()
def get_preinvoice_name(supplier, bill_no, tipo_dte):
    ajustes = frappe.get_single("ERPNext SII - Ajustes Generales")
    campo_rut = ajustes.campo_rut_proveedor or "tax_id"

    supplier_doc = frappe.get_doc("Supplier", supplier)
    proveedor_rut = getattr(supplier_doc, campo_rut, None)

    if not all([proveedor_rut, bill_no, tipo_dte]):
        return None

    return frappe.db.get_value("PreInvoice", {
        "rut_proveedor": proveedor_rut,
        "folio": bill_no,
        "tipo_dte": tipo_dte
    })
