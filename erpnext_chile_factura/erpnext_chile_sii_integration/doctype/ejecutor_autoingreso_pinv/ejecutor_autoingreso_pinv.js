frappe.ui.form.on('Ejecutor Autoingreso PINV', {
    refresh(frm) {
        // Deshabilitar edición si ya se ejecutó o falló
        if (["Ejecutado", "Error"].includes(frm.doc.status)) {
            frm.disable_save();
            frm.set_read_only();
        }

        // Deshabilitar el botón si no está en estado Pendiente
        frm.toggle_enable("ejecutar_autoingreso", frm.doc.status === "Pendiente");
    },

    ejecutar_autoingreso(frm) {
        if (frm.doc.status !== "Pendiente") {
            frappe.msgprint("⚠️ Solo puedes ejecutar este proceso si el estado es 'Pendiente'.");
            return;
        }

        if (frm.is_new()) {
            frappe.msgprint("💡 Debes guardar el documento antes de ejecutar el autoingreso.");
            return;
        }

        frappe.call({
            method: "erpnext_chile_factura.erpnext_chile_sii_integration.doctype.ejecutor_autoingreso_pinv.ejecutor_autoingreso_pinv.enqueue_autoingreso",
            args: { docname: frm.doc.name },
            callback: function (r) {
                frappe.msgprint(r.message || "Ejecutando en segundo plano…");
                frm.reload_doc();
            }
        });
    }
});
