import frappe
import re
from erpnext.buying.doctype.supplier.supplier import Supplier
from erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.sii_config import (
    get_rut_field_config,
    get_supplier_naming_config
)


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
        campo_rut = get_rut_field_config()
        valor_rut = getattr(self, campo_rut, None)

        if valor_rut:
            valor_rut = normalizar_rut(valor_rut)
            if frappe.db.exists("Supplier", valor_rut):
                frappe.throw(f"Ya existe un proveedor con el RUT: {valor_rut}")
            self.name = valor_rut
        else:
            super().autoname()

    def validate(self):
        super().validate()

        campo_rut = get_rut_field_config()
        valor_rut = getattr(self, campo_rut, None)

        if not valor_rut:
            frappe.throw(f"El campo RUT ({campo_rut}) es obligatorio.")

        valor_rut = normalizar_rut(valor_rut)

        if not rut_es_valido(valor_rut):
            frappe.throw(f"El RUT '{valor_rut}' no tiene un formato válido (Ej: 12345678-9 o K12345678-9).")

        setattr(self, campo_rut, valor_rut)
