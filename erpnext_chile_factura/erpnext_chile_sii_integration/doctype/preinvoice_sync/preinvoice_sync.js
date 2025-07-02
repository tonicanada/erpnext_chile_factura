frappe.ui.form.on('PreInvoice Sync', {
    refresh: function (frm) {
        console.log("Script cargado para PreInvoice Sync");

        // Mostrar campo executed solo si está marcado
        frm.set_df_property('executed', 'hidden', !frm.doc.executed);

        if (frm.doc.executed) {
            frm.disable_save();
            frm.set_df_property('sincronizar', 'hidden', 1);
            frm.set_intro("Este documento ya fue ejecutado. Cree uno nuevo si desea volver a sincronizar.", "blue");

            // Hacer campos clave de solo lectura
            frm.set_df_property('company', 'read_only', 1);
            frm.set_df_property('month', 'read_only', 1);
            frm.set_df_property('year', 'read_only', 1);
        } else {
            frm.set_df_property('sincronizar', 'hidden', 0);
        }

        // 🔁 Auto-refresh si el estado es "En proceso"
        if (frm.doc.status === "En proceso") {
            setTimeout(() => {
                console.log("Auto-recargando documento...");
                frm.reload_doc();
            }, 10000); // cada 10 segundos
        }
    },

    sincronizar: function (frm) {
        if (frm.is_new()) {
            frappe.msgprint("Debe guardar el documento antes de sincronizar.");
            return;
        }

        frappe.call({
            method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.preinvoice_sync.preinvoice_sync.sync_preinvoices",
            args: {
                docname: frm.doc.name
            },
            freeze: true,
            freeze_message: "Sincronizando con el SII, por favor espere...",
            callback: function (r) {
                if (!r.exc) {
                    frappe.msgprint("La sincronización ha sido iniciada. El estado se actualizará automáticamente.");
                    frm.reload_doc(); // primer reload rápido
                }
            }
        });
    }
});
