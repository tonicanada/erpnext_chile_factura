// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Ejecutor Autoingreso PINV", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on('Ejecutor Autoingreso PINV', {
    ejecutar_autoingreso: function (frm) {
        frappe.call({
            method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.ejecutor_autoingreso_pinv.ejecutor_autoingreso_pinv.ejecutar_autoingreso",
            args: { docname: frm.doc.name },
            callback: function (r) {
                frappe.msgprint("Autoingreso ejecutado.");
                frm.reload_doc();
            }
        });
    }
});