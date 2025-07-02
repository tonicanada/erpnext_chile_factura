# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.reglas import evaluate_autoingreso_rules
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.creador_factura import create_purchase_invoice_from_preinvoice


class PreInvoice(Document):
    pass


@frappe.whitelist()
def make_purchase_invoice_from_rules(preinvoice_name):
    doc = frappe.get_doc("PreInvoice", preinvoice_name)
    resultado = evaluate_autoingreso_rules(doc)

    if resultado:
        regla = resultado["regla"]
        acciones = resultado["acciones_sugeridas"]
        acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"
        pinv_name = create_purchase_invoice_from_preinvoice(doc, acciones)
        frappe.db.commit()
        return {"status": "ok", "message": f"Purchase Invoice {pinv_name} creada", "pinv": pinv_name}
    else:
        return {"status": "no_rule", "message": "No se aplicó ninguna regla"}
