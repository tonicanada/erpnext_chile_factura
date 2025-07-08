# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe.utils import now, now_datetime, get_site_path
from frappe.model.document import Document
from openpyxl import Workbook
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.reglas import evaluate_autoingreso_rules
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.creador_factura import create_purchase_invoice_from_preinvoice


class EjecutorAutoingresoPINV(Document):
    pass


def ejecutar_autoingreso(docname, preinvoice_names=None):
    frappe.logger().info(f"🚀 ejecutando autoingreso para {docname}")
    doc = frappe.get_doc("Ejecutor Autoingreso PINV", docname)

    doc.status = "En proceso"
    doc.fecha_ejecucion = now()
    doc.usuario_ejecucion = frappe.session.user
    doc.log_mensaje = ""
    doc.resultado_autoingreso_pinv = []

    resumen = {
        "pinv_creadas": 0,
        "proveedores_creados": 0,
        "descartadas_oc": 0,
        "descartadas_dte": 0,
        "sin_regla": [],
        "otros_descartes": [],
        "errores": []
    }

    excel_data = []

    if preinvoice_names:
        nombres = frappe.parse_json(preinvoice_names)
    else:
        preinvoices = frappe.get_all("PreInvoice",
                                     filters={"estado": "Confirmada",
                                              "pinv_creada": ["is", "not set"]},
                                     pluck="name")
        nombres = preinvoices

    for name in nombres:
        try:
            pre = frappe.get_doc("PreInvoice", name)
            resultado = evaluate_autoingreso_rules(pre)

            if isinstance(resultado, dict) and not resultado.get("descartada"):
                regla = resultado["regla"]
                acciones = resultado["acciones_sugeridas"]
                acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"

                resultado_creacion = create_purchase_invoice_from_preinvoice(
                    pre, acciones)
                pinv_name = resultado_creacion["pinv"]
                estado_pinv = frappe.db.get_value(
                    "Purchase Invoice", pinv_name, "docstatus")
                estado_label = "Submitted" if estado_pinv == 1 else "Draft"

                doc.append("resultado_autoingreso_pinv", {
                    "tipo": "PINV creada",
                    "preinvoice": pre.name,
                    "pinv": pinv_name,
                    "estado_pinv": estado_label,
                    "supplier": resultado_creacion["proveedor"],
                    "mensaje": f"Factura creada con regla {regla.name}",
                    "detalle_json": json.dumps({"acciones": acciones, "regla": regla.name}, ensure_ascii=False, indent=2)
                })
                resumen["pinv_creadas"] += 1
                excel_data.append(
                    [pre.name, "PINV creada", pinv_name, resultado_creacion["proveedor"], "", ""])

                if resultado_creacion.get("proveedor_creado"):
                    doc.append("resultado_autoingreso_pinv", {
                        "tipo": "Proveedor creado",
                        "preinvoice": pre.name,
                        "supplier": resultado_creacion["proveedor"],
                        "mensaje": "Proveedor creado automáticamente"
                    })
                    resumen["proveedores_creados"] += 1
                    excel_data.append(
                        [pre.name, "Proveedor creado", "", resultado_creacion["proveedor"], "", ""])

            elif isinstance(resultado, dict) and resultado.get("descartada"):
                razon = resultado.get("razon", "")
                if razon == "Ninguna regla aplica":
                    resumen["sin_regla"].append(pre.name)
                elif "referencia tipo 801" in razon:
                    resumen["descartadas_oc"] += 1
                elif "tipo DTE" in razon:
                    resumen["descartadas_dte"] += 1
                else:
                    resumen["otros_descartes"].append((pre.name, razon))
                excel_data.append([pre.name, "Descartada", "", "", razon, ""])

            else:
                resumen["otros_descartes"].append(
                    (pre.name, "Evaluación no retornó datos"))
                excel_data.append(
                    [pre.name, "Descartada", "", "", "Evaluación no retornó datos", ""])

        except Exception as e:
            resumen["errores"].append((name, str(e)))
            excel_data.append([name, "Error", "", "", str(e), ""])

    # Mensaje de resumen
    if len(nombres) == 1:
        fila = excel_data[0]
        mensaje = fila[4] if fila[4] else "Sin mensaje"
        doc.log_mensaje = (
            f"{fila[0]}: {fila[1]}"
            + (f" → {fila[2]}" if fila[2] else "")
            + (f" | Proveedor: {fila[3]}" if fila[3] else "")
            + f" | {mensaje}"
        )
    else:
        resumen_lines = [
            f"✔ {resumen['pinv_creadas']} PINV creadas",
            f"➕ {resumen['proveedores_creados']} proveedores creados",
            f"📦 {resumen['descartadas_oc']} descartadas por OC",
            f"📄 {resumen['descartadas_dte']} descartadas por tipo DTE",
        ]
        if len(resumen["sin_regla"]) == 1:
            resumen_lines.append(
                f"⚠ {resumen['sin_regla'][0]} sin regla aplicable")
        elif len(resumen["sin_regla"]) > 1:
            resumen_lines.append(
                f"⚠ {len(resumen['sin_regla'])} PreInvoices sin reglas aplicables")

        if resumen["otros_descartes"]:
            resumen_lines.append(
                f"⚠ {len(resumen['otros_descartes'])} descartadas por otras razones")
        if resumen["errores"]:
            resumen_lines.append(f"❌ {len(resumen['errores'])} con error")

        doc.log_mensaje = "\n".join(resumen_lines)

    doc.status = "Error" if resumen["errores"] else "Ejecutado"

    # Generar y adjuntar Excel
    if excel_data:
        filename = now_datetime().strftime("%Y%m%d") + "_log_ejecucion_autoingreso.xlsx"
        filepath = os.path.join(get_site_path("private", "files"), filename)
        wb = Workbook()
        ws = wb.active
        ws.title = "Resumen"
        ws.append(["PreInvoice", "Tipo", "PINV",
                  "Proveedor", "Mensaje", "Estado PINV"])
        for row in excel_data:
            ws.append(row)
        wb.save(filepath)

        # Adjuntar a la doc
        frappe.get_doc({
            "doctype": "File",
            "file_url": f"/private/files/{filename}",
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name,
            "folder": "Home/Attachments",
            "is_private": 1
        }).insert(ignore_permissions=True)

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
        frappe.throw(
            "⚠️ Ya existe un autoingreso en proceso. Espera a que finalice antes de ejecutar uno nuevo.")

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
