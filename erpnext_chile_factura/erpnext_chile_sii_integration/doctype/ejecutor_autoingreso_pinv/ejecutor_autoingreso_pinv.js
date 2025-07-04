frappe.ui.form.on('Ejecutor Autoingreso PINV', {
    refresh(frm) {
        // Si ya fue ejecutado o hubo error, no se puede volver a ejecutar
        if (["Ejecutado", "Error"].includes(frm.doc.status)) {
            frm.disable_save();
            frm.set_read_only();
        }

        // // Recargar periódicamente si está "En proceso"
        // if (frm.doc.status === "En proceso") {
        //     const interval = setInterval(() => {
        //         frappe.db.get_doc('Ejecutor Autoingreso PINV', frm.doc.name).then(doc => {
        //             if (doc.status === "Ejecutado" || doc.status === "Error") {
        //                 clearInterval(interval);
        //                 frm.reload_doc();
        //             }
        //         });
        //     }, 5000);
        // }
    },

    ejecutar_autoingreso(frm) {
        if (frm.is_new()) {
            frappe.msgprint("💡 Debes guardar el documento antes de ejecutar el autoingreso.");
            return;
        }

        frappe.call({
            method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.ejecutor_autoingreso_pinv.ejecutor_autoingreso_pinv.enqueue_autoingreso",
            args: { docname: frm.doc.name },
            callback: function (r) {
                frappe.msgprint(r.message || "Ejecutando en segundo plano…");
                frm.reload_doc(); // recarga para mostrar "En proceso"
            }
        });
    }
});
