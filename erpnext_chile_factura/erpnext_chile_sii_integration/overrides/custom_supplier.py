# erpnext_chile_factura/overrides/custom_supplier.py

import frappe
import re
from erpnext.buying.doctype.supplier.supplier import Supplier

def normalizar_rut(rut_raw: str) -> str:
    rut = rut_raw.strip().upper().replace(".", "").replace(" ", "")
    if "-" not in rut and len(rut) > 1:
        rut = f"{rut[:-1]}-{rut[-1]}"
    return rut

def rut_es_valido(rut: str) -> bool:
    """Valida sintácticamente un RUT chileno."""
    return re.match(r"^\d{7,8}-[\dK]$", rut.upper()) is not None

class CustomSupplier(Supplier):
    def autoname(self):
        if self.tax_id:
            rut = normalizar_rut(self.tax_id)
            if frappe.db.exists("Supplier", rut):
                frappe.throw(f"Ya existe un proveedor con el RUT: {rut}")
            self.name = rut
        else:
            super().autoname()

    def validate(self):
        super().validate()

        if not self.tax_id:
            frappe.throw("El campo RUT (tax_id) es obligatorio.")

        self.tax_id = normalizar_rut(self.tax_id)

        if not rut_es_valido(self.tax_id):
            frappe.throw(f"El RUT '{self.tax_id}' no tiene un formato válido (Ej: 12345678-9 o K12345678-9).")
