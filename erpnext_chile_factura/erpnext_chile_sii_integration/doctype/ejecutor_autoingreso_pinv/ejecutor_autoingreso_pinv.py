# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.utils import now
from frappe.model.document import Document
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.reglas import evaluate_autoingreso_rules
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.creador_factura import create_purchase_invoice_from_preinvoice


class EjecutorAutoingresoPINV(Document):
    pass


@frappe.whitelist()
def ejecutar_autoingreso(docname):
    doc = frappe.get_doc("Ejecutor Autoingreso PINV", docname)

    doc.fecha_ejecucion = now()
    doc.usuario_ejecucion = frappe.session.user
    doc.status = "Ejecutado"
    doc.log_mensaje = ""
    doc.resultado_autoingreso_pinv = []

    resumen_log = []
    errores = 0

    preinvoices = frappe.get_all("PreInvoice",
        filters={"estado": "Confirmada", "pinv_creada": ["is", "not set"]},
        fields=["name", "rut_proveedor"]
    )

    for p in preinvoices:
        try:
            pre = frappe.get_doc("PreInvoice", p.name)
            resultado = evaluate_autoingreso_rules(pre)

            if resultado:
                regla = resultado["regla"]
                acciones = resultado["acciones_sugeridas"]
                acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"

                resultado_creacion = create_purchase_invoice_from_preinvoice(pre, acciones)
                pinv_name = resultado_creacion["pinv"]

                estado_pinv = frappe.db.get_value("Purchase Invoice", pinv_name, "docstatus")
                estado_pinv_label = "Submitted" if estado_pinv == 1 else "Draft"

                doc.append("resultado_autoingreso_pinv", {
                    "tipo": "PINV creada",
                    "preinvoice": pre.name,
                    "pinv": pinv_name,
                    "estado_pinv": estado_pinv_label,
                    "supplier": pre.rut_proveedor,
                    "mensaje": f"Factura creada con regla {regla.name}",
                    "detalle_json": json.dumps({
                        "acciones": acciones,
                        "regla": regla.name
                    }, ensure_ascii=False, indent=2)
                })

                resumen_log.append(f"✔ {pre.name} → {pinv_name}")

                if resultado_creacion.get("proveedor_creado"):
                    doc.append("resultado_autoingreso_pinv", {
                        "tipo": "Proveedor creado",
                        "preinvoice": pre.name,
                        "supplier": resultado_creacion.get("proveedor"),
                        "mensaje": "Proveedor creado automáticamente",
                        "estado_pinv": "",
                        "detalle_json": ""
                    })
                    resumen_log.append(f"➕ Proveedor creado: {resultado_creacion['proveedor']}")

            # Si no hay regla, no se agrega nada

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Autoingreso fallo en {p.name}")
            doc.append("resultado_autoingreso_pinv", {
                "tipo": "Error",
                "preinvoice": p.name,
                "mensaje": str(e),
                "estado_pinv": "",
                "detalle_json": ""
            })
            errores += 1
            resumen_log.append(f"❌ {p.name}: {e}")

    doc.status = "Error" if errores else "Ejecutado"
    doc.log_mensaje = "\n".join(resumen_log[:10]) + ("\n..." if len(resumen_log) > 10 else "")
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return "Autoingreso completado"
