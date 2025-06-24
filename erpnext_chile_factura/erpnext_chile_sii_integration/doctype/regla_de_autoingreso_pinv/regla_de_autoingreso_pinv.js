// Copyright (c) 2025, Antonio Cañada Momblant and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Regla de Autoingreso PINV", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on('Regla de Autoingreso PINV', {
  setup: function(frm) {
    // Filtros por empresa receptora para todos los campos relevantes
    const campos_empresa = ["account", "cost_center", "project", "warehouse"];

    campos_empresa.forEach(field => {
      frm.set_query(field, function(doc) {
        if (!doc.empresa_receptora) {
          frappe.msgprint("Por favor, selecciona primero la Empresa Receptora.");
          return { filters: { name: "__no_value__" } };
        }

        let base_filters = { company: doc.empresa_receptora };

        // Solo para cost center y warehouse: excluir grupos
        if (["cost_center", "warehouse", "account"].includes(field)) {
          base_filters["is_group"] = 0;
        }

        return { filters: base_filters };
      });
    });
  },

  empresa_receptora: function(frm) {
    const depende = ["account", "cost_center", "project", "warehouse"];
    const habilitar = !!frm.doc.empresa_receptora;

    depende.forEach(f => {
      frm.set_df_property(f, "read_only", !habilitar);
    });
  }
});
