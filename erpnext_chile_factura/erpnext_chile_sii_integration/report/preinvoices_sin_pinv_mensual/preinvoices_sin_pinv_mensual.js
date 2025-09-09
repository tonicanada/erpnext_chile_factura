frappe.query_reports["Preinvoices sin Pinv Mensual"] = {
    filters: [
        {
            fieldname: "mes_libro_sii",
            label: "Mes Libro SII",
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start()
        }
    ],
    onload: function (report) {
        report.page.add_inner_button(__("Descargar XMLs en ZIP"), function () {
            let filters = report.get_values();
            frappe.call({
                method: "erpnext_chile_factura.erpnext_chile_sii_integration.report.preinvoices_sin_pinv_mensual.preinvoices_sin_pinv_mensual.download_xml_zip",
                args: { filters: filters },
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(r.message);  // ✅ muestra aviso al usuario
                        frappe.show_alert({
                            message: r.message,
                            indicator: "blue"
                        });
                    } else {
                        frappe.msgprint("No se generó ningún archivo ZIP.");
                    }
                }
            });
        });
    }
};
