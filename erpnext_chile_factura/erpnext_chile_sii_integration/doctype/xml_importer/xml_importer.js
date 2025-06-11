// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

// frappe.ui.form.on("XML Importer", {
// 	refresh(frm) {

// 	},
// });



frappe.ui.form.on('XML Importer', {
    procesar_zip: function(frm) {
        frappe.call({
            method: 'erpnext_chile_factura.erpnext_chile_sii_integration.doctype.xml_importer.xml_importer.procesar_xml_zip',
            args: {
                docname: frm.doc.name
            },
            callback: function(r) {
                frm.reload_doc();
                frappe.msgprint("Procesamiento completado.");
            },
            error: function(err) {
                frappe.msgprint("Ocurrió un error durante el procesamiento.");
            }
        });
    }
});