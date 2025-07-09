import os
import frappe
import json

def load_client_scripts_from_fixtures():
    path = os.path.join(
        frappe.get_app_path('erpnext_chile_factura'),
        'fixtures',
        'client_script.json'
    )

    if not os.path.exists(path):
        frappe.throw("No se encontró el archivo client_script.json")

    with open(path, 'r') as f:
        data = json.load(f)

    for script in data:
        if not frappe.db.exists("Client Script", script["name"]):
            doc = frappe.get_doc(script)
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f'Client Script "{doc.name}" insertado.')
        else:
            frappe.logger().info(f'Client Script "{script["name"]}" ya existe.')
