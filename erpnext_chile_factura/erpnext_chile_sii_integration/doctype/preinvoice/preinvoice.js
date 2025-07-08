frappe.ui.form.on('PreInvoice', {
  refresh: function (frm) {
    frm.disable_save();

    if (frm.doc.estado === "Confirmada" && !frm.doc.pinv_creada) {
      frm.add_custom_button("Crear PINV desde reglas", function () {
        frappe.call({
          method: "erpnext_chile_factura.erpnext_chile_sii_integration.autoingreso_pinv.utils.run_autoingreso_desde_preinvoice",
          args: {
            preinvoice_name: frm.doc.name
          },
          callback: function (r) {
            if (!r.exc && r.message) {
              frappe.msgprint(r.message.message); // mostrar solo el texto, no el objeto entero

              if (r.message.proveedor) {
                frappe.set_route("Form", "Supplier", r.message.proveedor);
              }

              if (r.message.ejecutor_name) {
                frappe.set_route("Form", "Ejecutor Autoingreso PINV", r.message.ejecutor_name);
              }
            }
          }
        });
      }, __("Acciones"));
    }
  }
});
