import frappe



def get_sii_ajustes_generales():
    """Obtiene el singleton de ajustes generales."""
    return frappe.get_single("ERPNext SII - Ajustes Generales")


def get_rut_field_config():
    """Devuelve el campo configurado como fuente del RUT del proveedor: 'tax_id' o 'rut'."""
    try:
        ajustes = get_sii_ajustes_generales()
        return ajustes.campo_rut_proveedor or "tax_id"
    except Exception:
        return "tax_id"  # fallback


def get_supplier_naming_config():
    """Devuelve si el nombre del proveedor será por RUT o nombre legal."""
    try:
        ajustes = get_sii_ajustes_generales()
        return ajustes.naming_supplier or "RUT"
    except Exception:
        return "RUT"  # fallback
