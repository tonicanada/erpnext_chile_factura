// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

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

            if (frm.doc.status === "Completado") {
                frm.set_intro("✅ El ZIP fue procesado correctamente.", "green");
            } else if (frm.doc.status === "Error") {
                frm.set_intro("❌ Hubo un error en el procesamiento. Puedes reintentarlo.", "red");

                frm.add_custom_button("🔁 Reintentar procesamiento", function () {
                    procesar_zip(frm);
                });
            } else if (frm.doc.status === "En proceso") {
                frm.set_intro("⏳ El ZIP está en proceso. Esta página se actualizará automáticamente.", "blue");

                const interval = setInterval(() => {
                    frappe.db.get_doc('XML Importer', frm.doc.name).then(updated => {
                        if (["Completado", "Error"].includes(updated.status)) {
                            clearInterval(interval);
                            frm.reload_doc();
                        }
                    });
                }, 5000);
            }
        } else {
            frm.set_df_property('procesar_zip', 'hidden', 0);
        }
    },

    procesar_zip: function (frm) {
        if (frm.is_new()) {
            frappe.msgprint("💡 Debes guardar el documento antes de procesar el ZIP.");
            return;
        }

        procesar_zip(frm);
    }
});

// Función común para procesar ZIP (inicio o reintento)
function procesar_zip(frm) {
    console.log("Procesando ZIP para", frm.doc.name);

    frappe.call({
        method: 'erpnext_chile_factura.erpnext_chile_sii_integration.doctype.xml_importer.xml_importer.procesar_xml_zip',
        args: {
            docname: frm.doc.name
        },
        callback: function (r) {
            console.log("Encolado con éxito:", r);
            frappe.msgprint("✅ El procesamiento se ha encolado. Espera unos segundos...");
        },
        error: function (err) {
            console.error("❌ Error en procesamiento:", err);
            frappe.msgprint("❌ Ocurrió un error al intentar encolar el procesamiento.");
        }
    });
}
