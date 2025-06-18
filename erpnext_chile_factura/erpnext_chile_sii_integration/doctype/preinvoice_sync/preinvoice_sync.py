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


@frappe.whitelist()
def sync_preinvoices(docname):
    doc = frappe.get_doc("PreInvoice Sync", docname)

    # Obtener empresa
    empresa = frappe.get_doc("Company", doc.company)
    rut_empresa = empresa.tax_id

    # Obtener configuración de SimpleAPI RCV
    try:
        config = frappe.get_doc("SimpleAPI RCV Setup", {
                                "company": doc.company})
    except frappe.DoesNotExistError:
        frappe.throw(
            f"No hay configuración de SimpleAPI RCV para la empresa {doc.company}")

    # Construir URL y headers
    url = config.url_api.format(month=str(doc.month).zfill(2), year=doc.year)

    API_BODY = {
        "RutUsuario": config.rut_usuario,
        "PasswordSII": config.get_password("password_sii"),
        "RutEmpresa": rut_empresa,
        "Ambiente": int(config.ambiente),
    }

    try:
        if not doc.month or not doc.year:
            frappe.throw("Mes y año no seleccionados")

        headers = {
            "Content-Type": "application/json",
            "Authorization": config.get_password("api_token")
        }
        
        response = requests.post(url, json=API_BODY, headers=headers)

        logger.info(API_BODY)
        logger.info(f"PasswordSII real (parcial): {config.password_sii[:3]}***")
        logger.info(f"Token API real (parcial): {config.api_token[:6]}***")

        if response.status_code != 200:
            doc.status = "Error"
            doc.result_summary = f"HTTP {response.status_code}: {response.text}"
            doc.save()
            return

        data = response.json()

        created = 0
        updated = 0

        # # Importa json de prueba
        # app_path = frappe.get_app_path("erpnext_chile_factura")
        # json_path = os.path.join(app_path, "erpnext_chile_sii_integration", "data", "sample_json_preinvoices.json")
        # with open(json_path, "r") as f:
        #     data = json.load(f)

        for entry in data["compras"]["detalleCompras"]:
            logger.info(f"Procesando entrada: {entry}")
            
            folio = entry.get("folio")
            rut_proveedor = entry.get("rutProveedor")
            tipo_dte = entry.get("tipoDTE")

            filters = {
                "folio": folio,
                "rut_proveedor": rut_proveedor,
                "tipo_dte": tipo_dte
            }

            existing = frappe.get_all("PreInvoice", filters=filters)

            if existing:
                preinv = frappe.get_doc("PreInvoice", existing[0].name)

                if preinv.estado != "Pendiente":
                    logger.info(
                        f"Saltando actualización para PreInvoice {preinv.name} porque estado = {preinv.estado}")
                    continue
            else:
                preinv = frappe.new_doc("PreInvoice")
                created += 1

            # Guardamos el estado anterior
            preinv_before = preinv.as_dict().copy()

            # Mapear campos simples
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

            # Tabla hija
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

            # Detectar cambios
            has_changes = False
            for field in field_map.values():
                new_value = normalize_value(preinv.get(field))
                old_value = normalize_value(preinv_before.get(field))
                if new_value != old_value:
                    logger.info(
                        f"Cambio detectado en {field}: {old_value} → {new_value}")
                    has_changes = True
                    break

            if not has_changes:
                old_table = preinv_before.get("otros_impuestos", [])
                new_table = preinv.get("otros_impuestos", [])
                if old_table != new_table:
                    has_changes = True

            if has_changes:
                preinv.company = doc.company
                preinv.save()
                logger.info(f"Actualizado PreInvoice {preinv.name}")
                if existing:
                    updated += 1
            else:
                logger.info(f"Sin cambios para PreInvoice {preinv.name}")

            doc.status = "Finalizado"
            doc.result_summary = f"Preinvoices creados: {created}, actualizados: {updated}"
            doc.executed_by = frappe.session.user
            doc.execution_date = now_datetime()
            doc.save()

    except Exception as e:
        logger.error(f"Error en la sincronización: {str(e)}", exc_info=True)
        doc.status = "Error"
        doc.result_summary = f"Excepción: {str(e)}"
        doc.executed_by = frappe.session.user
        doc.execution_date = now_datetime()
        doc.save()
