# Copyright (c) 2025, Antonio Cañada Momblant and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document


from frappe.model.document import Document
import frappe


class RegladeAutoingresoPINV(Document):
    def validate(self):

        if not self.enabled:
            return

        condiciones_actuales = [
            (c.campo, c.operador, c.valor, c.origen_dato) for c in self.condiciones]

        posibles = frappe.get_all(
            "Regla de Autoingreso PINV",
            filters={
                "empresa_receptora": self.empresa_receptora,
                "enabled": 1,
                "name": ["!=", self.name]
            },
            fields=["name"]
        )

        for r in posibles:
            otra = frappe.get_doc("Regla de Autoingreso PINV", r.name)
            condiciones_otra = [
                (c.campo, c.operador, c.valor, c.origen_dato) for c in otra.condiciones]

            if sorted(condiciones_actuales) == sorted(condiciones_otra):
                frappe.throw(
                    f"Ya existe una regla activa con las mismas condiciones: <b>{otra.name}</b>"
                )

        if self.accion_al_aplicar_regla == "Crear factura submitted":
            faltan = []

            if not self.account:
                faltan.append("Cuenta contable")
            if not self.cost_center:
                faltan.append("Centro de costo")
            if not self.item_sugerido:
                faltan.append("Ítem sugerido")
                
            if not self.project:
                faltan.append("Proyecto")
            else:
                # Verificar si el ítem sugerido es de stock y falta bodega
                item = frappe.get_doc("Item", self.item_sugerido)
                if item.is_stock_item and not self.warehouse:
                    faltan.append("Almacén (porque el ítem es de stock)")

            if faltan:
                frappe.throw(
                    "No puedes seleccionar 'Crear factura submitted' porque faltan los siguientes campos obligatorios:\n<ul>"
                    + "".join(f"<li>{campo}</li>" for campo in faltan)
                    + "</ul>"
                )
