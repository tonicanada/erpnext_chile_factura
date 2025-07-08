import frappe
import json
from frappe.utils import now
from frappe import _
from erpnext_chile_factura.erpnext_chile_sii_integration.doctype.ejecutor_autoingreso_pinv.ejecutor_autoingreso_pinv import (
    ejecutar_autoingreso,
)


@frappe.whitelist()
def run_autoingreso_desde_preinvoice(preinvoice_name):
    # Crear el documento ejecutor
    ejecutor = frappe.new_doc("Ejecutor Autoingreso PINV")
    ejecutor.insert(ignore_permissions=True)
    frappe.db.commit()

    # Ejecutar el autoingreso solo para esta PreInvoice
    resultados = ejecutar_autoingreso(
        docname=ejecutor.name, preinvoice_names=json.dumps([preinvoice_name])
    )

    # Extraer el nombre del proveedor desde los resultados, si existe
    proveedor_name = None
    if resultados and isinstance(resultados, list):
        primer_resultado = resultados[0]
        proveedor_name = primer_resultado.get("proveedor")

    return {
        "message": _("Autoingreso ejecutado para {0}").format(preinvoice_name),
        "ejecutor_name": ejecutor.name,
        "proveedor": proveedor_name,
    }


@frappe.whitelist()
def enqueue_autoingreso(docname, preinvoice_names=None):
    # Cambiar estado a "En proceso" antes de encolar
    doc = frappe.get_doc("Ejecutor Autoingreso PINV", docname)
    doc.status = "En proceso"
    doc.fecha_ejecucion = now()
    doc.usuario_ejecucion = frappe.session.user
    doc.save(ignore_permissions=True)

    frappe.enqueue(
        method="erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.ejecutor_autoingreso_pinv.ejecutar_autoingreso_background",
        queue="default",
        timeout=1800,
        now=False,
        docname=docname,
        preinvoice_names=preinvoice_names,
        user=frappe.session.user,
    )
