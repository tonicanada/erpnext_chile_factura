# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import os
import zipfile
from xml.etree import ElementTree as ET
from frappe.utils.file_manager import get_file, save_file
from frappe.utils import now
from frappe.model.document import Document

@frappe.whitelist()
def procesar_xml_zip(docname):
    doc = frappe.get_doc("XML Importer", docname)
    file_url = doc.archivo_zip

    if not file_url:
        frappe.throw("No se ha subido ningún archivo ZIP.")

    file_name, file_content = get_file(file_url)
    zip_path = frappe.utils.get_site_path("private", "xml_imports", f"{docname}.zip")
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, "wb") as f:
        f.write(file_content)

    extract_dir = frappe.utils.get_site_path("private", "xml_imports", f"{docname}_extracted")
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    ns = {"sii": "http://www.sii.cl/SiiDte"}
    logs = []

    for filename in os.listdir(extract_dir):
        if not filename.lower().endswith(".xml"):
            continue
        try:
            xml_path = os.path.join(extract_dir, filename)
            tree = ET.parse(xml_path)
            root = tree.getroot()
            documento = root.find(".//sii:Documento", ns)
            if not documento:
                logs.append(f"{filename}: Documento no encontrado.")
                continue

            rut = documento.findtext(".//sii:Emisor/sii:RUTEmisor", default="", namespaces=ns)
            folio = documento.findtext(".//sii:IdDoc/sii:Folio", default="", namespaces=ns)
            tipo = documento.findtext(".//sii:IdDoc/sii:TipoDTE", default="", namespaces=ns)

            preinvoice = frappe.get_all(
                "PreInvoice",
                filters={"rut_proveedor": rut, "folio": folio, "tipo_dte": int(tipo)},
                fields=["name"]
            )

            if not preinvoice:
                logs.append(f"{filename}: PreInvoice no encontrada (RUT: {rut}, Folio: {folio}, Tipo: {tipo})")
                continue

            pre = frappe.get_doc("PreInvoice", preinvoice[0].name)
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

            forma_pago = documento.findtext(".//sii:IdDoc/sii:FmaPago", default="", namespaces=ns)
            pre.xml_forma_pago = forma_pago

            pre.tiene_xml_importado = 1
            pre.fecha_importacion_xml = now()
            pre.save()

            # Adjuntar XML al PreInvoice
            save_file(
                fname=filename,
                content=open(xml_path, "rb").read(),
                dt="PreInvoice",
                dn=pre.name,
                folder=None,
                decode=False,
                is_private=True
            )

            logs.append(f"{filename}: XML importado correctamente en PreInvoice {pre.name}")
        except Exception as e:
            logs.append(f"{filename}: Error al procesar ({str(e)})")

    doc.db_set("log_resultado", "\n".join(logs))
    doc.db_set("status", "Completado")


class XMLImporter(Document):
    pass
