import frappe

def pinv_remove_reference_if_linked(doc, method):
    """
    Cuando una PINV se cancela o elimina, se borra el campo pinv_creada de la PreInvoice correspondiente.
    """
    preinvoice_name = frappe.db.get_value("PreInvoice", {"pinv_creada": doc.name}, "name")
    if preinvoice_name:
        frappe.db.set_value("PreInvoice", preinvoice_name, "pinv_creada", None)
        frappe.logger("pinv_creator").info(
            f"🗑️ Se eliminó referencia a PINV {doc.name} en PreInvoice {preinvoice_name} (trigger: {method})"
        )