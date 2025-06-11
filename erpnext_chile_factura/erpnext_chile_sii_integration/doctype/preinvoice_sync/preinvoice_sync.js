// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

frappe.ui.form.on('PreInvoice Sync', {
    refresh: function(frm) {
        console.log("Script cargado para Preinvoice Sync");
    },
    sincronizar: function(frm) {
        console.log("Botón sincronizar clickeado");

        frappe.call({
            method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.preinvoice_sync.preinvoice_sync.sync_preinvoices",
            args: {
                docname: frm.doc.name
            },
            callback: function(r) {
                if(!r.exc) {
                    console.log("HOLA");
                    frappe.msgprint("Sincronización completa");
                    frm.reload_doc();
                }
            }
        });
    }
});
