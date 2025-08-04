frappe.query_reports["Libro Compras Mensual PreInvoices"] = {
    filters: [
        {
            fieldname: "mes_libro_sii",
            label: "Mes Libro SII",
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start()
        }
    ]
};
