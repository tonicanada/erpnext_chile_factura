frappe.query_reports["Preinvoices sin Pinv Mensual"] = {
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
