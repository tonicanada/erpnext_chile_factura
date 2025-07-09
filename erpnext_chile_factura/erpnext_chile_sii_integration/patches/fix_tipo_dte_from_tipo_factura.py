import frappe

def execute():
    """
    Completa el campo tipo_dte en Purchase Invoice usando el campo tipo_factura.
    Pensado inicialmente para Tecton, pero aplicable a cualquier cliente con ese campo.
    """
    mapeo = {
        "Afecta": 33,
        "Electrónica": 33,
        "Exenta": 34,
        "Electrónica Exenta": 34,
        "Factura de compra interna": 46,
        "Nota de Crédito Electrónica": 61,
        "Nota de Débito Electrónica": 56,
        "Boleta Honorarios": None,
        "Factura proveedor extranjero": None,
    }

    facturas = frappe.get_all(
        "Purchase Invoice",
        filters={"posting_date": [">=", "2025-01-01"]},
        fields=["name", "tipo_factura", "tipo_dte"]
    )

    actualizadas = 0
    for factura in facturas:
        if factura.tipo_dte in (None, 0):
            nuevo_tipo_dte = mapeo.get(factura.tipo_factura)
            if nuevo_tipo_dte:
                frappe.db.set_value("Purchase Invoice", factura.name, "tipo_dte", nuevo_tipo_dte)
                actualizadas += 1

    frappe.db.commit()
    frappe.msgprint(f"Actualizadas {actualizadas} facturas con tipo_dte desde tipo_factura.")
