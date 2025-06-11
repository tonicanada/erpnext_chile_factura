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


def camel_to_snake(name):
    # Convierte tipoDTE → tipo_dte y tipoIVARecuperable → tipo_iva_recuperable
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

@frappe.whitelist()
def sync_preinvoices(docname):
    doc = frappe.get_doc("PreInvoice Sync", docname)

    try:
        # Si doc.month o doc.year no existen, arrojar mensaje frappe
        if not doc.month or not doc.year:
            raise Exception("Mes y año no seleccionados")
        
        url = API_URL_TEMPLATE.format(
            month=str(doc.month).zfill(2), year=doc.year)
        
        logger.info("Iniciando sincronización")
        
              
        # response = requests.post(url, json=API_BODY, headers={
        #                          "Content-Type": "application/json", "Authorization": "0792-W360-6385-5233-1973"})
        
        # data = response.json()
        
        response = {
            "status_code": 200
        }
        
        # Importa json de prueba
        app_path = frappe.get_app_path("erpnext_chile_factura")
        json_path = os.path.join(app_path, "erpnext_chile_sii_integration", "data", "sample_json_preinvoices.json")
        with open(json_path, "r") as f:
            data = json.load(f)
            
        frappe.msgprint(str(len(data["compras"]["detalleCompras"])))
        
        # Logear el json de data
        logger.info("Respuesta de la API:\n%s", json.dumps(data, indent=2, ensure_ascii=False))

        # if response.status_code != 200:
        if False:
            doc.status = "Error"
            doc.result_summary = f"HTTP {response.status_code}: {response.text}"
        else:
            # data = response.json()

            created = 0
            for entry in data["compras"]["detalleCompras"]:
                folio = entry.get("folio")
                rut_proveedor = entry.get("rutProveedor")

                preinvoice = frappe.get_all("PreInvoice", filters={
                    "folio": folio, "rut_proveedor": rut_proveedor
                })

                if not preinvoice:
                    new_doc = frappe.new_doc("PreInvoice")
                    
                    for field in entry:
                        snake_field = camel_to_snake(field)
                        if new_doc.meta.get_field(snake_field):
                            new_doc.set(snake_field, entry[field])
                    
                    new_doc.insert()
                    created += 1
        doc.status = "Finalizado"
        doc.result_summary = f"Facturas nuevas creadas: {created}"
        doc.save()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "PreInvoice Sync Error")
        doc.status = "Error"
        doc.result_summary = str(e)
        doc.execution_date = now_datetime()
        doc.executed_by = frappe.session.user
        doc.save()
        return f"Error en la sincronización: {str(e)}"
