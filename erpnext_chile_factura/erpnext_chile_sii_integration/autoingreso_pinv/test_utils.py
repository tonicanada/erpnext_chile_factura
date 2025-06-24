import frappe
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.reglas import evaluate_autoingreso_rules
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.creador_factura import create_purchase_invoice_from_preinvoice

def test_autoingreso_para_preinvoice(nombre_preinvoice):
    """
    Permite probar el autoingreso de una PINV desde una PreInvoice específica.
    """
    preinvoice = frappe.get_doc("PreInvoice", nombre_preinvoice)

    resultado = evaluate_autoingreso_rules(preinvoice)
    if not resultado:
        frappe.msgprint("No se encontró ninguna regla aplicable.")
        return

    acciones = resultado["acciones_sugeridas"]
    regla = resultado["regla"]
    acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"

    pinv_name = create_purchase_invoice_from_preinvoice(preinvoice, acciones)
    frappe.msgprint(f"PINV creada exitosamente: {pinv_name}")
