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
def ejecutar_autoingreso(docname, preinvoice_names=None):
    frappe.logger().info(f"🚀 ejecutando autoingreso para {docname}")
    doc = frappe.get_doc("Ejecutor Autoingreso PINV", docname)

    doc.status = "En proceso"
    doc.fecha_ejecucion = now()
    doc.usuario_ejecucion = frappe.session.user
    doc.log_mensaje = ""
    doc.resultado_autoingreso_pinv = []

    resumen_log = []
    errores = 0

    # Parsear la lista si viene como JSON desde JS
    if preinvoice_names:
        nombres = frappe.parse_json(preinvoice_names)
    else:
        preinvoices = frappe.get_all("PreInvoice",
                                     filters={"estado": "Confirmada",
                                              "pinv_creada": ["is", "not set"]},
                                     fields=["name"]
                                     )
        nombres = [p.name for p in preinvoices]

    for name in nombres:
        try:
            pre = frappe.get_doc("PreInvoice", name)
            resultado = evaluate_autoingreso_rules(pre)

            if resultado:
                regla = resultado["regla"]
                acciones = resultado["acciones_sugeridas"]
                acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"

                resultado_creacion = create_purchase_invoice_from_preinvoice(
                    pre, acciones)
                pinv_name = resultado_creacion["pinv"]

                estado_pinv = frappe.db.get_value(
                    "Purchase Invoice", pinv_name, "docstatus")
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
                    resumen_log.append(
                        f"➕ Proveedor creado: {resultado_creacion['proveedor']}")
            else:
                pass
                # doc.append("resultado_autoingreso_pinv", {
                #     "tipo": "Sin regla",
                #     "preinvoice": pre.name,
                #     "mensaje": "No se aplicó ninguna regla",
                #     "estado_pinv": "",
                #     "detalle_json": ""
                # })
                # resumen_log.append(f"⚠ {pre.name}: No se aplicó ninguna regla")

        except Exception as e:
            frappe.log_error(frappe.get_traceback(),
                             f"Autoingreso fallo en {name}")
            doc.append("resultado_autoingreso_pinv", {
                "tipo": "Error",
                "preinvoice": name,
                "mensaje": str(e),
                "estado_pinv": "",
                "detalle_json": ""
            })
            errores += 1
            resumen_log.append(f"❌ {name}: {e}")

    doc.status = "Error" if errores else "Ejecutado"
    doc.log_mensaje = "\n".join(
        resumen_log[:10]) + ("\n..." if len(resumen_log) > 10 else "")
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return "Autoingreso completado"




@frappe.whitelist()
def enqueue_autoingreso(docname):
    from frappe.utils.background_jobs import enqueue

    # Verificar si ya hay otro proceso en ejecución
    en_proceso = frappe.get_all(
        "Ejecutor Autoingreso PINV",
        filters={"status": "En proceso", "name": ["!=", docname]},
        limit=1
    )

    if en_proceso:
        frappe.throw("⚠️ Ya existe un autoingreso en proceso. Espera a que finalice antes de ejecutar uno nuevo.")

    # Continuar normalmente
    doc = frappe.get_doc("Ejecutor Autoingreso PINV", docname)
    doc.status = "En proceso"
    doc.fecha_ejecucion = frappe.utils.now()
    doc.usuario_ejecucion = frappe.session.user or "Administrator"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    frappe.enqueue(
        "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.ejecutor_autoingreso_pinv.ejecutor_autoingreso_pinv.ejecutar_autoingreso",
        queue="default",
        timeout=600,
        now=False,
        docname=docname
    )

    return "⏳ Autoingreso en ejecución. Puedes recargar en unos segundos."
