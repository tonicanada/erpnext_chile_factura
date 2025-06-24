import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def create_tipo_dte_field():
    custom_fields = {
        "Purchase Invoice": [
            {
                "fieldname": "tipo_dte",
                "label": "Tipo DTE",
                "fieldtype": "Int",
                "insert_after": "tax_id",  # o el campo que prefieras
                "read_only": 0,
                "hidden": 0,
                "print_hide": 0
            }
        ]
    }

    create_custom_fields(custom_fields, update=True)
