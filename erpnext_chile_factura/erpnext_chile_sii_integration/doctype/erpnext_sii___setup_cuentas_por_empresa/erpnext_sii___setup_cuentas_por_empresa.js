// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

// frappe.ui.form.on("ERPNext SII - Setup cuentas por empresa", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on('ERPNext SII - Setup cuentas por empresa', {
  setup: function(frm) {
    frm.fields_dict['cuentas'].grid.get_field('account').get_query = function(doc, cdt, cdn) {
      if (!doc.empresa) {
        frappe.msgprint("Por favor, selecciona primero la Empresa.");
        return { filters: { name: "__no_value__" } };
      }

      return {
        filters: {
          company: doc.empresa,
          is_group: 0
        }
      };
    };
  }
});