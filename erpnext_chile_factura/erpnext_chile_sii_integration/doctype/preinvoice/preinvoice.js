frappe.ui.form.on('PreInvoice', {
  onload: function (frm) {
    make_preinvoice_read_only(frm);
  },
  refresh: function (frm) {
    make_preinvoice_read_only(frm);

    // Agregar botón solo si corresponde
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

function make_preinvoice_read_only(frm) {
  frm.set_read_only();
  frm.disable_save();

  const readOnlyTables = [
    "items",
    "referencias",
    "emisor_detalle",
    "transporte",
    "descuentos_recargos",
    "otros_impuestos"
  ];

  readOnlyTables.forEach(fieldname => {
    frm.set_df(fieldname, { read_only: 1 });

    const grid = frm.fields_dict[fieldname]?.grid;
    if (grid) {
      grid.can_add_rows = false;
      grid.wrapper.find('.grid-add-row').hide();
      grid.wrapper.find('.grid-remove-rows').hide();
      grid.wrapper.find('.grid-buttons').hide();
      grid.refresh();
    }
  });
}
