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


API_URL_TEMPLATE = "https://servicios.simpleapi.cl/api/RCV/compras/{month}/{year}"
API_BODY = {
    "RutUsuario": "13459205-2",
    "PasswordSII": "Alicia12",
    "RutEmpresa": "76407152-2",
    "Ambiente": 1,
    "Detallado": True
}


# def camel_to_snake(name):
#     # Convierte tipoDTE → tipo_dte y tipoIVARecuperable → tipo_iva_recuperable
#     s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
#     return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

@frappe.whitelist()
def sync_preinvoices(docname):
    doc = frappe.get_doc("PreInvoice Sync", docname)

    try:
        if not doc.month or not doc.year:
            frappe.throw("Mes y año no seleccionados")

        url = API_URL_TEMPLATE.format(
            year=doc.year, month=str(doc.month).zfill(2)
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": "0792-W360-6385-5233-1973"  # pon aquí tu token real
        }

        response = requests.post(url, json=API_BODY, headers=headers)

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
                    logger.info(f"Saltando actualización para PreInvoice {preinv.name} porque estado = {preinv.estado}")
                    continue

                updated += 1
            else:
                preinv = frappe.new_doc("PreInvoice")
                created += 1

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
                "codigoIvaNoRecuperable": "codigo_iva_no_recuperable",
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

            # Limpia tabla hija si ya tenía valores
            preinv.set("otros_impuestos", [])

            # Procesamiento seguro de otrosImpuestos
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

            preinv.save()

        doc.status = "Finalizado"
        doc.result_summary = f"Preinvoices creados: {created}, actualizados: {updated}"
        doc.save()

    except Exception as e:
        logger.error(f"Error en la sincronización: {str(e)}", exc_info=True)
        doc.status = "Error"
        doc.result_summary = f"Excepción: {str(e)}"
        doc.save()