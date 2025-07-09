import frappe
import os
import pandas as pd
from frappe.utils import get_site_path
from datetime import datetime
from frappe import get_doc



def normalizar_rut(rut):
    return rut.replace(".", "").replace("-", "").strip().lower()

def rut_sin_dv(rut):
    r = normalizar_rut(rut)
    return r[:-1] if len(r) > 1 else r

def execute():
    ajustes = frappe.get_single("ERPNext SII - Ajustes Generales")
    campo_rut = ajustes.campo_rut_proveedor or "tax_id"

    DTE_A_FACTURA = {
        33: "Afecta",
        34: "Exenta",
        46: "Factura de compra interna",
        61: "Nota de Crédito Electrónica",
        56: "Nota de Débito Electrónica"
    }

    resultados = []
    margen = 2  # pesos CLP

    pinvs = frappe.get_all(
        "Purchase Invoice",
        filters={
            "posting_date": [">=", "2025-01-01"],
            "docstatus": 1
        },
        fields=["name", campo_rut, "bill_no", "tipo_dte", "tipo_factura", "rounded_total"]
    )

    for pinv in pinvs:
        rut_pinv_raw = pinv.get(campo_rut) or ""
        rut_norm = normalizar_rut(rut_pinv_raw)
        rut_sdv = rut_sin_dv(rut_norm)
        folio = pinv.bill_no
        tipo_dte = pinv.tipo_dte
        tipo_factura = pinv.tipo_factura
        monto_pinv = float(pinv.rounded_total or 0)

        if not rut_norm or not folio:
            continue

        # Buscar PreInvoice exacta
        exact_matches = frappe.get_all(
            "PreInvoice",
            filters={
                "rut_proveedor": ["like", f"%{rut_sdv}%"],
                "folio": folio,
                "tipo_dte": tipo_dte
            },
            fields=["name", "rut_proveedor", "monto_total"]
        )
        exact_matches = [
            pre for pre in exact_matches
            if normalizar_rut(pre.rut_proveedor) == rut_norm
        ]

        if exact_matches:
            pre = exact_matches[0]
            resultados.append({
                "pinv": pinv.name,
                "rut_pinv": rut_pinv_raw,
                "folio": folio,
                "tipo_dte_pinv": tipo_dte,
                "tipo_factura_pinv": tipo_factura,
                "tipo_dte_preinvoice": tipo_dte,
                "tipo_factura_corregida": None,
                "monto_total_pinv": monto_pinv,
                "monto_total_preinvoice": float(pre.monto_total or 0),
                "accion": "Correcta"
            })
            continue

        # Buscar por RUT + folio (ignorar tipo_dte), comparar monto absoluto
        candidates = frappe.get_all(
            "PreInvoice",
            filters={
                "rut_proveedor": ["like", f"%{rut_sdv}%"],
                "folio": folio
            },
            fields=["name", "rut_proveedor", "tipo_dte", "monto_total"]
        )
        candidates = [
            pre for pre in candidates
            if normalizar_rut(pre.rut_proveedor) == rut_norm
        ]

        if candidates:
            pre = candidates[0]
            tipo_dte_real = pre.tipo_dte
            monto_pre = float(pre.monto_total or 0)
            if abs(abs(monto_pre) - abs(monto_pinv)) <= margen:
                frappe.db.set_value("Purchase Invoice", pinv.name, "tipo_dte", tipo_dte_real)
                nueva_factura = DTE_A_FACTURA.get(tipo_dte_real)
                if nueva_factura:
                    frappe.db.set_value("Purchase Invoice", pinv.name, "tipo_factura", nueva_factura)
                resultados.append({
                    "pinv": pinv.name,
                    "rut_pinv": rut_pinv_raw,
                    "folio": folio,
                    "tipo_dte_pinv": tipo_dte,
                    "tipo_factura_pinv": tipo_factura,
                    "tipo_dte_preinvoice": tipo_dte_real,
                    "tipo_factura_corregida": nueva_factura,
                    "monto_total_pinv": monto_pinv,
                    "monto_total_preinvoice": monto_pre,
                    "accion": "Corregida desde PreInvoice (mismo monto)"
                })
                continue

        # Sin coincidencia válida
        resultados.append({
            "pinv": pinv.name,
            "rut_pinv": rut_pinv_raw,
            "folio": folio,
            "tipo_dte_pinv": tipo_dte,
            "tipo_factura_pinv": tipo_factura,
            "tipo_dte_preinvoice": None,
            "tipo_factura_corregida": None,
            "monto_total_pinv": monto_pinv,
            "monto_total_preinvoice": None,
            "accion": "Sin PreInvoice compatible"
        })

    frappe.db.commit()

    if resultados:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{now_str}_pinv_dte_auditoria.xlsx"
        ruta_archivo = os.path.join(get_site_path("private", "files"), nombre_archivo)

        df = pd.DataFrame(resultados)
        df.to_excel(ruta_archivo, index=False)
                

        print(f"✅ Auditoría finalizada. Excel guardado:")
        print(f"   ➜ /private/files/{nombre_archivo}")
    else:
        print("ℹ️ No se generó Excel porque no hubo resultados.")
