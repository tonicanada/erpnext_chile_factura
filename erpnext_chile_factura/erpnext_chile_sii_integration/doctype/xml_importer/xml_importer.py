# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

import frappe
import os
import zipfile
from xml.etree import ElementTree as ET
from frappe.utils.file_manager import get_file
from frappe.model.document import Document

@frappe.whitelist()
def procesar_xml_zip(docname):
    doc = frappe.get_doc("XML Importer", docname)
    file_url = doc.archivo_zip

    if not file_url:
        frappe.throw("No se ha subido ningún archivo ZIP.")

    # Obtener archivo desde Frappe y guardarlo como ZIP físico
    file_name, file_content = get_file(file_url)
    zip_path = frappe.utils.get_site_path("private", "xml_imports", f"{docname}.zip")
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, "wb") as f:
        f.write(file_content)

    # Carpeta donde descomprimir el contenido
    extract_dir = frappe.utils.get_site_path("private", "xml_imports", f"{docname}_extracted")
    os.makedirs(extract_dir, exist_ok=True)

    # Descomprimir ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Namespaces y logs
    ns = {"sii": "http://www.sii.cl/SiiDte"}
    logs = []

    for file in os.listdir(extract_dir):
        if not file.lower().endswith(".xml"):
            continue
        try:
            file_path = os.path.join(extract_dir, file)
            tree = ET.parse(file_path)
            root = tree.getroot()

            documento = root.find(".//sii:Documento", ns)
            if not documento:
                logs.append(f"{file}: Documento no encontrado")
                continue

            rut = documento.findtext(".//sii:Emisor/sii:RUTEmisor", default="N/A", namespaces=ns)
            folio = documento.findtext(".//sii:IdDoc/sii:Folio", default="N/A", namespaces=ns)
            fecha = documento.findtext(".//sii:IdDoc/sii:FchEmis", default="N/A", namespaces=ns)
            tipo = documento.findtext(".//sii:IdDoc/sii:TipoDTE", default="N/A", namespaces=ns)
            monto = documento.findtext(".//sii:Totales/sii:MntTotal", default="N/A", namespaces=ns)

            logs.append(f"{file}: RUT {rut}, Folio {folio}, Fecha {fecha}, Tipo {tipo}, Monto {monto}")
        except Exception as e:
            logs.append(f"{file}: Error al procesar ({str(e)})")

    # Guardar resultado en el DocType
    doc.db_set("log_resultado", "\n".join(logs))
    doc.db_set("status", "Completado")

class XMLImporter(Document):
    pass
