frappe.ui.form.on('PreInvoice', {
  refresh: function (frm) {
    // Desactiva guardar para evitar ediciones
    frm.disable_save();

    // Agregar botón si la preinvoice está confirmada y aún no tiene PINV
    if (frm.doc.estado === "Confirmada" && !frm.doc.pinv_creada) {
      frm.add_custom_button("Crear PINV desde reglas", function () {
        frappe.call({
          method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.preinvoice.preinvoice.make_purchase_invoice_from_rules",
          args: { preinvoice_name: frm.doc.name },
          callback: function (r) {
            if (!r.exc) {
              frappe.msgprint(r.message);
              frm.reload_doc();
            }
          }
        });
      }, __("Acciones"));
    }
  }
});
