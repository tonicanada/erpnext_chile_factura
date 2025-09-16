import frappe

logger = frappe.logger("autoingreso_preinv")
logger.setLevel("INFO")

TIPOS_DTE_VALIDOS = [33, 34, 46]  # Factura electrónica, exenta, compra
TIPO_REFERENCIA_OC = 801

CAMPO_ALIAS_PREINVOICE_ITEM = {
    "nombre_item": "xml_nombre_producto",
    "codigo_producto": "xml_codigo_producto",
    "descripcion_producto": "xml_descripcion_producto",
    "cantidad": "xml_cantidad",
    "unidad_medida": "xml_unidad_medida",
    "precio_unitario": "xml_precio_unitario",
    "monto_total": "xml_monto_total",
    "codigo_impuesto": "xml_codigo_impuesto"
}


def evaluate_autoingreso_rules(preinvoice_doc):
    logger.info(f"🔍 Evaluando reglas para PreInvoice {preinvoice_doc.name}")
    try:
        if preinvoice_doc.estado != "Confirmada":
            logger.info(
                f"❌ PreInvoice {preinvoice_doc.name} descartada: no está confirmada")
            return {"descartada": True, "razon": "Estado no confirmado"}

        if preinvoice_doc.tipo_dte not in TIPOS_DTE_VALIDOS:
            logger.info(
                f"❌ PreInvoice {preinvoice_doc.name} descartada: tipo DTE {preinvoice_doc.tipo_dte} no válido")
            return {"descartada": True, "razon": f"Tipo DTE {preinvoice_doc.tipo_dte} no válido"}


        reglas = frappe.get_all("Regla de Autoingreso PINV",
                                filters={
                                    "enabled": 1, "empresa_receptora": preinvoice_doc.empresa_receptora},
                                order_by="modified desc",
                                fields=["name"])

        for r in reglas:
            regla_doc = frappe.get_doc("Regla de Autoingreso PINV", r.name)
            
            if condiciones_se_cumplen(regla_doc, preinvoice_doc):
                # Si cumple condiciones, entonces mirar OC
                if tiene_referencia_a_oc(preinvoice_doc) and not getattr(regla_doc, "ignorar_referencia_oc", 0):
                    razon = f"Tiene referencia tipo 801 y la regla {regla_doc.name} no permite ignorarla"
                    logger.info(f"❌ PreInvoice {preinvoice_doc.name} descartada: {razon}")
                    return {"descartada": True, "razon": razon}
                
                logger.info(
                    f"✅ Se aplica regla {regla_doc.name} a PreInvoice {preinvoice_doc.name}")
                return {
                    "regla": regla_doc,
                    "acciones_sugeridas": {
                        "item": regla_doc.item_sugerido,
                        "account": regla_doc.account,
                        "cost_center": regla_doc.cost_center,
                        "warehouse": regla_doc.warehouse,
                        "project": regla_doc.project,
                    }
                }

        logger.info(
            f"🟡 Ninguna regla aplica a PreInvoice {preinvoice_doc.name}")
        return {"descartada": True, "razon": "Ninguna regla aplica"}

    except Exception as e:
        logger.error(f"❌ Error en evaluate_autoingreso_rules: {e}")
        frappe.log_error(frappe.get_traceback(),
                         "Error en evaluate_autoingreso_rules")
        return {"descartada": True, "razon": "Error al evaluar reglas"}


def tiene_referencia_a_oc(preinvoice_doc):
    referencias = frappe.get_all("PreInvoice Referencia",
                                 filters={"parent": preinvoice_doc.name,
                                          "xml_tipo_documento": TIPO_REFERENCIA_OC},
                                 limit=1)
    return bool(referencias)


def condiciones_se_cumplen(regla_doc, preinvoice_doc):
    for cond in regla_doc.condiciones:
        valor_real = obtener_valor_condicion(preinvoice_doc, cond)
        resultado = comparar(valor_real, cond.operador, cond.valor)
        logger.info(
            f"   ↪ Condición: {cond.campo} {cond.operador} {cond.valor} | Valor real: {valor_real} → {'✅' if resultado else '❌'}")
        if not resultado:
            return False
    return True


def obtener_valor_condicion(preinvoice_doc, cond):
    origen = cond.origen_dato
    campo = normalizar_nombre_campo(cond.campo)

    if origen == "preinvoice":
        return getattr(preinvoice_doc, campo, None)
    elif origen == "preinvoice_item":
        items = []

        if campo == "nombre_y_descripcion_item":
            items = frappe.get_all("PreInvoice Item", filters={"parent": preinvoice_doc.name},
                                   fields=["xml_nombre_producto", "xml_descripcion_producto"])
            for item in items:
                nombre = item.get("xml_nombre_producto", "") or ""
                descripcion = item.get("xml_descripcion_producto", "") or ""
                valor_completo = f"{nombre} {descripcion}".strip()
                if comparar(valor_completo, cond.operador, cond.valor):
                    return valor_completo
            return None
        else:
            items = frappe.get_all("PreInvoice Item", filters={
                                   "parent": preinvoice_doc.name}, fields=[campo])
            for item in items:
                valor_item = item.get(campo)
                if comparar(valor_item, cond.operador, cond.valor):
                    return valor_item
            return None
    elif origen == "preinvoice_emisor_detalle":
        detalles = frappe.get_all("PreInvoice Emisor Detalle", filters={
                                  "parent": preinvoice_doc.name}, fields=[campo])
        return detalles[0][campo] if detalles else None

    return None


def comparar(valor_real, operador, valor_condicion):
    if valor_real is None:
        return False

    try:
        if operador == "=":
            return str(valor_real) == valor_condicion
        elif operador == "≠":
            return str(valor_real) != valor_condicion
        elif operador == ">":
            return float(valor_real) > float(valor_condicion)
        elif operador == "<":
            return float(valor_real) < float(valor_condicion)
        elif operador == "≥":
            return float(valor_real) >= float(valor_condicion)
        elif operador == "≤":
            return float(valor_real) <= float(valor_condicion)
        elif operador == "contiene":
            return valor_condicion.lower() in str(valor_real).lower()
        elif operador == "no contiene":
            return valor_condicion.lower() not in str(valor_real).lower()
    except Exception as e:
        logger.warning(
            f"⚠️ Error al comparar {valor_real} {operador} {valor_condicion}: {e}")
        return False

    return False


def normalizar_nombre_campo(campo):
    return campo.strip().lower().replace(" ", "_").replace("í", "i").replace("ó", "o")
