# xml_processor.py final (usando save_file en lugar de save_file_on_filesystem)

import frappe
from frappe.utils import now
from frappe.utils.file_manager import save_file
from xml.etree import ElementTree as ET


def procesar_xml_content(xml_content: bytes, file_name: str = None) -> str:
    ns = {"sii": "http://www.sii.cl/SiiDte"}
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        return f"{file_name or 'XML'}: Error al parsear XML: {str(e)}"

    documento = root.find(".//sii:Documento", ns)
    if not documento:
        return f"{file_name or 'XML'}: Documento no encontrado"

    tipo_dte = documento.findtext(
        ".//sii:IdDoc/sii:TipoDTE", default="", namespaces=ns)
    if tipo_dte == "52":
        return f"{file_name or 'XML'}: Guía de despacho detectada"

    rut = documento.findtext(
        ".//sii:Emisor/sii:RUTEmisor", default="", namespaces=ns)
    folio = documento.findtext(
        ".//sii:IdDoc/sii:Folio", default="", namespaces=ns)

    preinvoice = frappe.get_all("PreInvoice", filters={
        "rut_proveedor": rut,
        "folio": folio,
        "tipo_dte": int(tipo_dte)
    }, fields=["name"])

    if not preinvoice:
        return f"{file_name or 'XML'}: PreInvoice no encontrada (RUT: {rut}, Folio: {folio}, Tipo: {tipo_dte})"

    pre = frappe.get_doc("PreInvoice", preinvoice[0].name)

    if pre.tiene_xml_importado:
        return f"{file_name or 'XML'}: Ya tenía un XML importado, omitiendo."
    pre.set("items", [])
    pre.set("referencias", [])
    pre.set("emisor_detalle", [])

    for det in root.findall(".//sii:Detalle", ns):
        pre.append("items", {
            "xml_codigo_producto": det.findtext("sii:CdgItem/sii:VlrCodigo", default="", namespaces=ns),
            "xml_nombre_producto": det.findtext("sii:NmbItem", default="", namespaces=ns),
            "xml_descripcion_producto": det.findtext("sii:DscItem", default="", namespaces=ns),
            "xml_cantidad": det.findtext("sii:QtyItem", default="", namespaces=ns),
            "xml_unidad_medida": det.findtext("sii:UnmdItem", default="", namespaces=ns),
            "xml_precio_unitario": det.findtext("sii:PrcItem", default="", namespaces=ns),
            "xml_monto_total": det.findtext("sii:MontoItem", default="", namespaces=ns),
            "xml_codigo_impuesto": det.findtext("sii:CodImpAdic", default="", namespaces=ns)
        })

    for ref in root.findall(".//sii:Referencia", ns):
        pre.append("referencias", {
            "xml_numero_linea": ref.findtext("sii:NroLinRef", default="", namespaces=ns),
            "xml_tipo_documento": ref.findtext("sii:TpoDocRef", default="", namespaces=ns),
            "xml_folio_referencia": ref.findtext("sii:FolioRef", default="", namespaces=ns),
            "xml_fecha_referencia": ref.findtext("sii:FchRef", default="", namespaces=ns),
            "xml_codigo_referencia": ref.findtext("sii:CodRef", default="", namespaces=ns),
            "xml_razon_referencia": ref.findtext("sii:RazonRef", default="", namespaces=ns),
        })

    emisor = root.find(".//sii:Emisor", ns)
    if emisor:
        pre.append("emisor_detalle", {
            "xml_giro": emisor.findtext("sii:GiroEmis", default="", namespaces=ns),
            "xml_telefono": emisor.findtext("sii:Telefono", default="", namespaces=ns),
            "xml_email": emisor.findtext("sii:CorreoEmisor", default="", namespaces=ns),
            "xml_actividad_economica": emisor.findtext("sii:Acteco", default="", namespaces=ns),
            "xml_sucursal": emisor.findtext("sii:Sucursal", default="", namespaces=ns),
            "xml_direccion": emisor.findtext("sii:DirOrigen", default="", namespaces=ns),
            "xml_comuna": emisor.findtext("sii:CmnaOrigen", default="", namespaces=ns),
            "xml_ciudad": emisor.findtext("sii:CiudadOrigen", default="", namespaces=ns),
            "xml_codigo_sii_sucursal": emisor.findtext("sii:CdgSIISucur", default="", namespaces=ns),
            "xml_codigo_vendedor": emisor.findtext("sii:CdgVendedor", default="", namespaces=ns),
        })

    forma_pago = documento.findtext(
        ".//sii:IdDoc/sii:FmaPago", default="", namespaces=ns)
    pre.xml_forma_pago = forma_pago

    if file_name:
        save_file(
            fname=file_name,
            content=xml_content,
            dt="PreInvoice",
            dn=pre.name,
            folder=None,
            decode=False,
            is_private=True
        )

    pre.tiene_xml_importado = 1
    pre.fecha_importacion_xml = now()
    pre.save()
    frappe.db.commit()

    return f"{file_name or 'XML'}: XML importado correctamente en PreInvoice {pre.name}"
