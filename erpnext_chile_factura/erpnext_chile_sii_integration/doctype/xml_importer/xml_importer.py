# xml_importer.py optimizado usando xml_processor

import frappe
import os
import zipfile
from frappe.utils.file_manager import get_file
from frappe.utils import now
from frappe.model.document import Document
from erpnext_chile_factura.erpnext_chile_sii_integration.utils.xml_processor import procesar_xml_content

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

    logs = []

    for filename in os.listdir(extract_dir):
        if not filename.lower().endswith(".xml"):
            continue
        try:
            xml_path = os.path.join(extract_dir, filename)
            with open(xml_path, "rb") as xml_file:
                content = xml_file.read()
            mensaje = procesar_xml_content(content, filename)
            logs.append(mensaje)
        except Exception as e:
            logs.append(f"{filename}: Error al procesar ({str(e)})")

    doc.db_set("log_resultado", "\n".join(logs))
    doc.db_set("status", "Completado")


class XMLImporter(Document):
    pass
