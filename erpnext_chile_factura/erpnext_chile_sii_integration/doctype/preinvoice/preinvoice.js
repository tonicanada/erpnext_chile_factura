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
              frappe.msgprint(r.message);
              if (r.ejecutor_name) {
                frappe.set_route("Form", "Ejecutor Autoingreso PINV", r.ejecutor_name);
              }
            }
          }
        });
      }, __("Acciones"));
    }
  }
});
