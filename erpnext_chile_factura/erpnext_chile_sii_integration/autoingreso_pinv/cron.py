import frappe
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.reglas import evaluate_autoingreso_rules
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.creador_factura import create_purchase_invoice_from_preinvoice

logger = frappe.logger("autoingreso_preinv")
logger.setLevel("INFO")

def autoingreso_preinvoices():
    """
    Recorre todas las PreInvoices confirmadas y sin PINV, evalúa reglas y crea Purchase Invoices si corresponde.
    """
    logger.info("🌀 Iniciando ejecución del cron de autoingreso de PreInvoices")

    preinvoices = frappe.get_all("PreInvoice", 
        filters={"estado": "Confirmada"},  # Puedes ajustar si usas campo "tiene_pinv"
        fields=["name"]
    )

    logger.info(f"🔍 Se encontraron {len(preinvoices)} PreInvoices en estado Confirmada")

    for p in preinvoices:
        try:
            logger.info(f"📄 Procesando PreInvoice {p.name}")
            preinvoice_doc = frappe.get_doc("PreInvoice", p.name)
            resultado = evaluate_autoingreso_rules(preinvoice_doc)

            if resultado:
                regla = resultado["regla"]
                acciones = resultado["acciones_sugeridas"]
                acciones["submit"] = regla.accion_al_aplicar_regla == "Crear factura submitted"

                pinv_name = create_purchase_invoice_from_preinvoice(preinvoice_doc, acciones)

                frappe.db.commit()

                logger.info(f"✅ PreInvoice {p.name} convertida en Purchase Invoice {pinv_name}")
            else:
                logger.info(f"🟡 No se aplicó ninguna regla a PreInvoice {p.name}")

        except Exception as e:
            logger.error(f"❌ Error al procesar PreInvoice {p.name}: {e}")
            frappe.log_error(frappe.get_traceback(), f"Autoingreso PINV fallo en {p.name}")

    logger.info("✅ Cron de autoingreso finalizado")
