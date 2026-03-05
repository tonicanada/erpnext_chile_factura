# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.file_manager import get_file
from frappe.utils.background_jobs import get_redis_conn, get_queue, execute_job, get_queues_timeout
import logging
import json
from datetime import date, timedelta
logger = frappe.logger("preinvoice_sync")

logger.setLevel(logging.INFO)

GLOBAL_SIMPLEAPI_LOCK_KEY = "erpnext_chile_factura:simpleapi_rcv_global_lock"
LOCK_RETRY_DELAYS_SECONDS = [300, 600]


class SimpleAPIGlobalLockBusyError(Exception):
    pass


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
    def validate(self):
        fiscal_year_name = str(self.year)

        exists = frappe.db.exists("Fiscal Year", fiscal_year_name)
        if not exists:
            frappe.throw(
                f"El año {self.year} no corresponde a ningún 'Fiscal Year' creado en el sistema. "
                f"Por favor verifique en: Configuración > Año Fiscal."
            )
    pass


def _get_certificado_pfx(config):
    if not config.certificado_pfx:
        frappe.throw(
            f"Falta el Certificado PFX en SimpleAPI RCV Setup para la empresa {config.company}."
        )

    try:
        cert_filename, cert_content = get_file(config.certificado_pfx)
    except Exception as e:
        frappe.throw(
            f"No se pudo leer el Certificado PFX ({config.certificado_pfx}) para la empresa {config.company}: {str(e)}"
        )

    if isinstance(cert_content, str):
        cert_content = cert_content.encode("utf-8")

    return cert_filename, cert_content


def _run_with_global_simpleapi_lock(fn, blocking_timeout=360, lock_timeout=900):
    redis_conn = get_redis_conn()
    lock = redis_conn.lock(
        GLOBAL_SIMPLEAPI_LOCK_KEY,
        timeout=lock_timeout,
        blocking_timeout=blocking_timeout,
    )

    acquired = lock.acquire(blocking=True)
    if not acquired:
        raise SimpleAPIGlobalLockBusyError(
            "SimpleAPI en uso por otro sitio (lock global activo). Reintente en unos segundos."
        )

    try:
        return fn()
    finally:
        try:
            lock.release()
        except Exception:
            pass


def _enqueue_sync_all_companies_retry(retry_attempt, delay_seconds):
    method = (
        "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.preinvoice_sync.preinvoice_sync.sync_all_companies"
    )
    queue_name = "long"
    queue_timeout = get_queues_timeout().get(queue_name) or 1500

    queue_args = {
        "site": frappe.local.site,
        "user": "Administrator",
        "method": method,
        "event": None,
        "job_name": method,
        "is_async": True,
        "kwargs": {"retry_attempt": retry_attempt},
    }

    q = get_queue(queue_name, is_async=True)
    q.enqueue_in(
        timedelta(seconds=delay_seconds),
        execute_job,
        timeout=queue_timeout,
        kwargs=queue_args,
        failure_ttl=frappe.conf.get("rq_job_failure_ttl"),
        result_ttl=frappe.conf.get("rq_results_ttl"),
    )

    logger.warning(
        f"[CRON] Reintentando sync_all_companies para sitio {frappe.local.site} en {delay_seconds}s "
        f"(intento {retry_attempt}/{len(LOCK_RETRY_DELAYS_SECONDS)}) por lock global ocupado."
    )


def _sync_preinvoices_from_api(company_name, year, month, created_by="Administrator"):

    empresa = frappe.get_doc("Company", company_name)
    rut_empresa = empresa.tax_id

    config = frappe.get_doc("SimpleAPI RCV Setup", {"company": company_name})

    url = config.url_api.format(month=str(month).zfill(2), year=year)

    api_token = config.get_password("api_token")
    cert_password = config.get_password("password_sii")

    if not api_token:
        frappe.throw(
            f"Falta Token API en SimpleAPI RCV Setup para la empresa {company_name}."
        )

    if not config.rut_usuario:
        frappe.throw(
            f"Falta RUT Certificado en SimpleAPI RCV Setup para la empresa {company_name}."
        )

    if not cert_password:
        frappe.throw(
            f"Falta Password Certificado en SimpleAPI RCV Setup para la empresa {company_name}."
        )

    cert_filename, cert_content = _get_certificado_pfx(config)

    api_input = {
        "RutCertificado": config.rut_usuario,
        "RutEmpresa": rut_empresa,
        "Ambiente": int(config.ambiente),
        "Password": cert_password,
    }

    headers = {
        "Authorization": api_token
    }

    data = {
        "input": json.dumps(api_input)
    }

    files = {
        "certificado": (cert_filename, cert_content, "application/x-pkcs12")
    }

    def _do_request():
        return requests.post(url, data=data, files=files, headers=headers, timeout=120)

    response = _run_with_global_simpleapi_lock(_do_request)

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
            # if preinv.estado != "Pendiente":
            #     continue
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
                
        # 👇 Agrega esta línea aquí:
        preinv.set("mes_libro_sii", date(year, month, 1))
        

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
            
        # Comparar también mes_libro_sii o forzar si antes estaba vacío
        if not preinv_before.get("mes_libro_sii") or normalize_value(preinv.get("mes_libro_sii")) != normalize_value(preinv_before.get("mes_libro_sii")):
            has_changes = True
            

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

    if doc.executed:
        frappe.throw(
            "Este documento ya fue ejecutado. Cree uno nuevo para volver a sincronizar.")

    # Marcar ejecución para evitar doble clics
    doc.executed_by = frappe.session.user
    doc.execution_date = now_datetime()
    doc.status = "En proceso"
    doc.executed = 1
    doc.result_summary = "Sincronización en curso..."
    doc.save()
    frappe.db.commit()

    frappe.enqueue(
        "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.preinvoice_sync.preinvoice_sync._enqueue_sync_task",
        queue="long",
        timeout=600,
        now=False,
        docname=docname
    )


def _enqueue_sync_task(docname):
    doc = frappe.get_doc("PreInvoice Sync", docname)

    try:
        result = _sync_preinvoices_from_api(
            doc.company, doc.year, int(doc.month))

        doc.status = "Finalizado"
        doc.result_summary = (
            f"Preinvoices creados: {result['creados']}, actualizados: {result['actualizados']}"
        )
    except Exception as e:
        logger.error(
            f"Error en la sincronización manual: {str(e)}", exc_info=True)
        doc.status = "Error"
        doc.result_summary = f"Excepción: {str(e)}"

    doc.save()
    frappe.db.commit()



def sync_all_companies(retry_attempt=0):
    from frappe.utils import getdate
    from datetime import date

    empresas = frappe.get_all("Company", pluck="name")

    def get_months_to_sync():
        today = date.today()
        year = today.year
        month = today.month

        months = [(year, month)]
        if today.day <= 8:
            if month == 1:
                months.append((year - 1, 12))
            else:
                months.append((year, month - 1))
        return months

    for nombre_empresa in empresas:
        for year, month in get_months_to_sync():
            try:
                result = _sync_preinvoices_from_api(
                    nombre_empresa, year, month)
                frappe.logger("preinvoice_sync").info(
                    f"[CRON] {nombre_empresa} {month:02d}-{year} OK - {result['creados']} creados, {result['actualizados']} actualizados"
                )
            except SimpleAPIGlobalLockBusyError as e:
                if retry_attempt < len(LOCK_RETRY_DELAYS_SECONDS):
                    delay_seconds = LOCK_RETRY_DELAYS_SECONDS[retry_attempt]
                    _enqueue_sync_all_companies_retry(
                        retry_attempt=retry_attempt + 1,
                        delay_seconds=delay_seconds
                    )
                else:
                    frappe.logger("preinvoice_sync").error(
                        f"[CRON] Lock global ocupado y máximo de reintentos alcanzado "
                        f"(sitio={frappe.local.site}, empresa={nombre_empresa}, mes={month:02d}-{year}): {str(e)}",
                        exc_info=True
                    )
                return
            except Exception as e:
                frappe.logger("preinvoice_sync").error(
                    f"[CRON] {nombre_empresa} {month:02d}-{year} ERROR - {str(e)}",
                    exc_info=True
                )
