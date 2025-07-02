// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

// frappe.ui.form.on("XML Importer", {
// 	refresh(frm) {

// 	},
// });



frappe.ui.form.on('XML Importer', {
    refresh: function (frm) {
        const is_processed = frm.doc.status && frm.doc.status !== "";

        if (is_processed) {
            frm.disable_save();
            frm.set_df_property('procesar_zip', 'hidden', 1);

            const read_only_fields = [
                'archivo_zip',
                'tipo_documento',
                'status',
                'fecha_carga',
                'log_resultado'
            ];

            read_only_fields.forEach(field => {
                frm.set_df_property(field, 'read_only', 1);
            });

            frm.set_intro("Este documento ya fue procesado. Cree uno nuevo para cargar otro ZIP.", "blue");
        } else {
            frm.set_df_property('procesar_zip', 'hidden', 0);
        }
    },

    procesar_zip: function (frm) {
        if (frm.is_new()) {
            frappe.msgprint("Debe guardar el documento antes de procesar el ZIP.");
            return;
        }

        frappe.call({
            method: 'erpnext_chile_factura.erpnext_chile_sii_integration.doctype.xml_importer.xml_importer.procesar_xml_zip',
            args: {
                docname: frm.doc.name
            },
            freeze: true,
            freeze_message: "Procesando ZIP, por favor espere...",
            callback: function () {
                frappe.msgprint("Procesamiento completado.");
                frm.reload_doc();
            },
            error: function () {
                frappe.msgprint("Ocurrió un error durante el procesamiento.");
            }
        });
    }
});
