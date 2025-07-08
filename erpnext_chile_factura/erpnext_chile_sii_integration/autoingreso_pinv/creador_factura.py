import frappe
import json

from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.sii_config import (
    get_rut_field_config,
    get_supplier_naming_config,
    get_sii_ajustes_generales,
)


logger = frappe.logger("pinv_creator")
logger.setLevel("INFO")


def create_purchase_invoice_from_preinvoice(preinvoice_doc, acciones):
    logger.info(f"🧾 Iniciando creación de PINV desde PreInvoice {preinvoice_doc.name}")

    rut_proveedor = preinvoice_doc.rut_proveedor
    campo_rut = get_rut_field_config()

    logger.info(f"🔧 Campo RUT configurado: {campo_rut}")
    logger.info(f"🔍 Buscando proveedor con {campo_rut} = {rut_proveedor}")

    proveedor_creado = ensure_supplier_exists(rut_proveedor, preinvoice_doc)

    # Muy importante: pedir explícitamente el 'name'
    supplier_name = frappe.get_value("Supplier", {campo_rut: rut_proveedor}, "name")

    logger.info(f"🎯 Resultado búsqueda: supplier_name = {supplier_name}")

    if not supplier_name:
        frappe.throw(f"No se encontró proveedor con {campo_rut} = {rut_proveedor}")

    if not supplier_name:
        logger.error(f"❌ No se encontró proveedor con RUT {rut_proveedor}")
        frappe.throw(f"No se encontró proveedor con RUT {rut_proveedor}")

    existente = frappe.get_all(
        "Purchase Invoice",
        filters={
            "supplier": supplier_name,
            "bill_no": str(preinvoice_doc.folio),
            "tipo_dte": preinvoice_doc.tipo_dte,
        },
        limit=1,
    )

    if existente:
        logger.warning(
            f"⚠️ Ya existe PINV para proveedor {supplier_name}, folio {preinvoice_doc.folio}, tipo DTE {preinvoice_doc.tipo_dte} → {existente[0].name}"
        )
        frappe.throw(
            f"Ya existe una PINV con el mismo RUT, folio y tipo DTE (doc: {existente[0].name})"
        )

    pinv = frappe.new_doc("Purchase Invoice")
    pinv.supplier = supplier_name
    pinv.posting_date = preinvoice_doc.fecha_emision
    pinv.company = preinvoice_doc.empresa_receptora
    pinv.bill_no = str(preinvoice_doc.folio)
    pinv.bill_date = preinvoice_doc.fecha_emision
    pinv.tipo_dte = preinvoice_doc.tipo_dte

    forma_pago = getattr(preinvoice_doc, "xml_forma_pago", None)
    try:
        forma_pago = int(forma_pago)
    except (TypeError, ValueError):
        forma_pago = None

    if forma_pago == 1:
        pinv.due_date = preinvoice_doc.fecha_emision
    elif forma_pago == 2:
        pinv.due_date = frappe.utils.add_days(preinvoice_doc.fecha_emision, 30)
    else:
        pinv.due_date = preinvoice_doc.fecha_emision

    item_code = acciones.get("item")
    if not item_code:
        logger.error(
            f"❌ No se definió un ítem válido para crear la factura para PreInvoice {preinvoice_doc.name}"
        )
        frappe.throw("No se definió un ítem válido para crear la factura")

    monto_item = (preinvoice_doc.monto_neto or 0) + (preinvoice_doc.monto_exento or 0)

    item_row = {
        "item_code": item_code,
        "qty": 1,
        "rate": monto_item,
        "amount": monto_item,
        "expense_account": acciones.get("account"),
        "cost_center": acciones.get("cost_center"),
        "project": acciones.get("project"),
    }

    if acciones.get("warehouse"):
        item_row["warehouse"] = acciones["warehouse"]

    pinv.append("items", item_row)

    if preinvoice_doc.monto_iva_recuperable:
        cuenta_iva = get_cuenta_configurada(
            preinvoice_doc.empresa_receptora, "iva_credito_fiscal"
        )
        pinv.append(
            "taxes",
            {
                "charge_type": "Actual",
                "account_head": cuenta_iva,
                "description": "IVA",
                "tax_amount": preinvoice_doc.monto_iva_recuperable,
            },
        )

    otros_impuestos = frappe.get_all(
        "PreInvoice Otros Impuestos",
        filters={"parent": preinvoice_doc.name},
        fields=["valor", "codigo"],
    )

    for imp in otros_impuestos:
        pinv.append(
            "taxes",
            {
                "charge_type": "Actual",
                "account_head": "",
                "description": f"Otro impuesto código {imp.codigo}",
                "tax_amount": imp.valor,
            },
        )

    logger.info(f"📌 Se asignará proveedor '{supplier_name}' al documento Purchase Invoice")
    pinv.insert()
    logger.info(
        f"✅ Purchase Invoice {pinv.name} creada desde PreInvoice {preinvoice_doc.name}"
    )
    frappe.db.commit()

    preinvoice_doc.db_set("pinv_creada", pinv.name)

    if abs(pinv.rounded_total - preinvoice_doc.monto_total) > 1:
        logger.error(
            f"❌ Descuadre en totales. PINV: {pinv.rounded_total}, PreInvoice: {preinvoice_doc.monto_total}"
        )
        frappe.throw(
            f"El total de la PINV ({pinv.rounded_total}) no coincide con el de la PreInvoice ({preinvoice_doc.monto_total})"
        )

    if acciones.get("submit"):
        pinv.submit()
        logger.info(f"📤 Purchase Invoice {pinv.name} enviada (submit)")

    return {
        "pinv": pinv.name,
        "proveedor_creado": proveedor_creado,
        "proveedor": supplier_name,
    }


def ensure_supplier_exists(rut_proveedor, preinvoice_doc):
    campo_rut = get_rut_field_config()
    naming = get_supplier_naming_config()

    existe = frappe.get_value("Supplier", {campo_rut: rut_proveedor})
    if existe:
        return False

    logger.info(f"🏢 Creando proveedor con RUT {rut_proveedor}")

    detalles = frappe.get_all(
        "PreInvoice Emisor Detalle",
        filters={"parent": preinvoice_doc.name},
        limit=1,
        fields=["xml_giro", "xml_direccion", "xml_email", "xml_ciudad"],
    )
    if not detalles:
        logger.error(
            f"❌ No se encontraron detalles del emisor para PreInvoice {preinvoice_doc.name}"
        )
        frappe.throw("No se encontraron detalles del emisor para crear el proveedor")

    detalle = detalles[0]
    razon_social = proper_case(preinvoice_doc.razon_social or rut_proveedor)
    direccion = proper_case(detalle.xml_direccion or "")
    giro = detalle.xml_giro or ""
    email = detalle.xml_email or None

    supplier = frappe.new_doc("Supplier")
    supplier.supplier_type = "Company"
    supplier.country = "Chile"
    supplier.supplier_details = giro
    if email:
        supplier.email_id = email

    # Asignar nombre según config
    supplier.supplier_name = (
        razon_social if naming == "Nombre del proveedor" else rut_proveedor
    )

    # Asignar RUT en el campo correspondiente
    if campo_rut == "rut":
        supplier.rut = rut_proveedor
    else:
        supplier.tax_id = rut_proveedor

    supplier.insert(ignore_permissions=True)
    supplier_name = supplier.name

    address = frappe.new_doc("Address")
    address.address_title = razon_social
    address.address_line1 = direccion
    address.country = "Chile"
    ciudad = proper_case(detalle.xml_ciudad or "") or "Santiago"
    address.city = ciudad
    if email:
        address.email_id = email

    address.append("links", {"link_doctype": "Supplier", "link_name": supplier_name})

    address.insert(ignore_permissions=True)
    frappe.db.commit()

    logger.info(f"✅ Proveedor {supplier_name} creado exitosamente")
    return True


def proper_case(texto):
    siglas_exentas = {
        "sa",
        "s.a.",
        "spa",
        "s.p.a.",
        "eirl",
        "ltda",
        "l.t.d.a.",
        "srl",
        "ltd.",
    }
    excepciones = {"de", "del", "la", "y", "en", "e"}

    def es_sigla(palabra):
        palabra_normalizada = palabra.lower().replace(".", "")
        return palabra_normalizada in {s.replace(".", "") for s in siglas_exentas}

    def capitalizar_palabra(palabra, posicion):
        palabra_lower = palabra.lower()

        if es_sigla(palabra):
            return palabra.upper()

        elif "-" in palabra:
            partes = palabra.split("-")
            return "-".join(
                [
                    capitalizar_palabra(parte, posicion if i == 0 else -1)
                    for i, parte in enumerate(partes)
                ]
            )

        elif palabra_lower in excepciones and posicion != 0:
            return palabra_lower

        else:
            return palabra.capitalize()

    palabras = texto.strip().split()
    return " ".join([capitalizar_palabra(p, i) for i, p in enumerate(palabras)])


def get_cuenta_configurada(empresa, tipo_cuenta):
    setup = frappe.get_all(
        "ERPNext SII - Setup cuentas por empresa",
        filters={"empresa": empresa},
        limit=1,
        fields=["name"],
    )

    if not setup:
        frappe.throw(
            f"No se encontró configuración de cuentas para la empresa '{empresa}'"
        )

    cuentas = frappe.get_all(
        "ERPNext SII - Cuenta Configurada",
        filters={"parent": setup[0].name, "tipo_cuenta": tipo_cuenta},
        limit=1,
        fields=["account"],
    )

    if not cuentas:
        frappe.throw(
            f"No se encontró cuenta configurada para '{tipo_cuenta}' en la empresa '{empresa}'"
        )

    return cuentas[0].account
