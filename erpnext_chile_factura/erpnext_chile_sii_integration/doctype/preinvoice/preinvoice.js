frappe.ui.form.on('PreInvoice', {
	onload: function (frm) {
		frm.set_read_only();  // Todo el formulario read-only
		frm.disable_save();   // Oculta botón "Guardar"

		// Asegurarse de que todas las tablas hijas también sean solo lectura
		const readOnlyTables = [
			"items",
			"referencias",
			"emisor_detalle",
			"transporte",
			"descuentos_recargos",
			"otros_impuestos"
		];

		readOnlyTables.forEach(fieldname => {
			frm.set_df(fieldname, {
				read_only: 1
			});
		});
	},
	refresh: function (frm) {
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
