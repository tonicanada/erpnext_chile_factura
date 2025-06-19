# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.model.document import Document
from frappe.utils import now_datetime
import logging
import json
import os
import re
logger = frappe.logger("preinvoice_sync")

logger.setLevel(logging.INFO)


def normalize_value(value):
    from datetime import datetime
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except:
            return value
    if value in [None, '', 0.0]:
        return 0  # considera None, '', 0.0 como 0
    return value


class PreInvoiceSync(Document):

    def sync_preinvoices(self):
        # Obtener mes y año señeccionados
        month = int(self.month)
        year = self.year

        # Construir fechas para la API, ej: '2025-05'
        periodo = f"{year}-{month:02d}"

        frappe.msgprint(f"Sincronización completada para {periodo}")

        return periodo

    pass


def _real_sync(company_name, year, month, created_by="Administrator"):
    import frappe
    from frappe.utils import now_datetime
    from datetime import datetime
    

    empresa = frappe.get_doc("Company", company_name)
    rut_empresa = empresa.tax_id

    config = frappe.get_doc("SimpleAPI RCV Setup", {"company": company_name})

    url = config.url_api.format(month=str(month).zfill(2), year=year)

    API_BODY = {
        "RutUsuario": config.rut_usuario,
        "PasswordSII": config.get_password("password_sii"),
        "RutEmpresa": rut_empresa,
        "Ambiente": int(config.ambiente),
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": config.get_password("api_token")
    }

    response = requests.post(url, json=API_BODY, headers=headers)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    created = 0
    updated = 0

    for entry in data["compras"]["detalleCompras"]:
        folio = entry.get("folio")
        rut_proveedor = entry.get("rutProveedor")
        tipo_dte = entry.get("tipoDTE")

        filters = {
            "folio": folio,
            "rut_proveedor": rut_proveedor,
            "tipo_dte": tipo_dte
        }

        existing = frappe.get_all("PreInvoice", filters=filters)
        preinv_is_existing = bool(existing)

        if preinv_is_existing:
            preinv = frappe.get_doc("PreInvoice", existing[0].name)
            if preinv.estado != "Pendiente":
                continue
        else:
            preinv = frappe.new_doc("PreInvoice")

        preinv_before = preinv.as_dict().copy()

        field_map = {
            "tipoDTE": "tipo_dte",
            "tipoCompra": "tipo_compra",
            "rutProveedor": "rut_proveedor",
            "razonSocial": "razon_social",
            "folio": "folio",
            "fechaEmision": "fecha_emision",
            "fechaRecepcion": "fecha_recepcion",
            "acuseRecibo": "acuse_recibo",
            "montoExento": "monto_exento",
            "montoNeto": "monto_neto",
            "montoIvaRecuperable": "monto_iva_recuperable",
            "montoIvaNoRecuperable": "monto_iva_no_recuperable",
            "codigoIvaNoRecuperable": "codigo_iva_no_retenido",
            "montoTotal": "monto_total",
            "montoNetoActivoFijo": "monto_neto_activo_fijo",
            "ivaActivoFijo": "iva_activo_fijo",
            "ivaUsoComun": "iva_uso_comun",
            "impuestoSinDerechoCredito": "impuesto_sin_derecho_a_credito",
            "ivaNoRetenido": "iva_no_retenido",
            "tabacosPuros": "tabacos_puros",
            "tabacosCigarrillos": "tabacos_cigarrillos",
            "tabacosElaborados": "tabacos_elaborados",
            "nceNdeFacturaCompra": "nce_n_de_factura_compra",
            "estado": "estado",
            "fechaAcuse": "fecha_acuse"
        }

        for source, target in field_map.items():
            if source in entry:
                preinv.set(target, entry[source])

        preinv.set("otros_impuestos", [])
        otros_impuestos = entry.get("otrosImpuestos")
        if isinstance(otros_impuestos, str):
            try:
                otros_impuestos = json.loads(otros_impuestos)
            except Exception:
                otros_impuestos = []

        if isinstance(otros_impuestos, list):
            for impuesto in otros_impuestos:
                if isinstance(impuesto, dict):
                    preinv.append("otros_impuestos", {
                        "valor": impuesto.get("valor"),
                        "tasa": impuesto.get("tasa"),
                        "codigo": impuesto.get("codigo")
                    })

        has_changes = False
        for field in field_map.values():
            new_value = normalize_value(preinv.get(field))
            old_value = normalize_value(preinv_before.get(field))
            if new_value != old_value:
                has_changes = True
                break

        if not has_changes:
            if preinv_before.get("otros_impuestos", []) != preinv.get("otros_impuestos", []):
                has_changes = True
                
                
        if has_changes or not preinv_is_existing:
            preinv.empresa_receptora = company_name
            if preinv_is_existing:
                preinv.save()
                updated += 1
                logger.info(f"[AUTO] Actualizado PreInvoice {preinv.name}")
            else:
                preinv.insert()
                created += 1
                logger.info(f"[AUTO] Insertado PreInvoice {preinv.name}")
        
        frappe.db.commit()

    return {
        "creados": created,
        "actualizados": updated,
        "errores": 0,
    }


@frappe.whitelist()
def sync_preinvoices(docname):
    doc = frappe.get_doc("PreInvoice Sync", docname)

    try:
        result = _real_sync(doc.company, doc.year, int(
            doc.month), created_by=frappe.session.user)

        doc.status = "Finalizado"
        doc.result_summary = f"Preinvoices creados: {result['creados']}, actualizados: {result['actualizados']}"
    except Exception as e:
        logger.error(
            f"Error en la sincronización manual: {str(e)}", exc_info=True)
        doc.status = "Error"
        doc.result_summary = f"Excepción: {str(e)}"

    doc.executed_by = frappe.session.user
    doc.execution_date = now_datetime()
    doc.save()


def sync_all_companies():
    from frappe.utils import getdate
    from datetime import datetime

    hoy = getdate()
    current_month = hoy.month
    current_year = hoy.year

    empresas = frappe.get_all("Company", pluck="name")

    for nombre_empresa in empresas:
        try:
            result = _real_sync(nombre_empresa, current_year, current_month)
            frappe.logger("preinvoice_sync").info(
                f"[CRON] {nombre_empresa} OK - {result['creados']} creados, {result['actualizados']} actualizados"
            )
        except Exception as e:
            frappe.logger("preinvoice_sync").error(
                f"[CRON] {nombre_empresa} ERROR - {str(e)}", exc_info=True
            )
