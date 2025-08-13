# Notas Técnicas - Client Script Autocompletar `tipo_dte`

## Descripción

Este Client Script autocompleta el campo `tipo_dte` en el Doctype **Purchase Invoice** a partir del valor del campo `tipo_factura`.

## Consideraciones

- El campo `tipo_factura` **no es estándar en ERPNext**, por lo que el script verifica si existe antes de actuar.  
- Está pensado principalmente para la empresa **Constructora Tecton**, donde se añadió dicho campo.  
- Si la empresa no tiene este campo, el script no realiza ninguna acción, manteniendo la compatibilidad.  
- Esta implementación permite que la app sea reusable y segura en entornos con o sin `tipo_factura`.

## Patches relacionados

Para Constructora Tecton existen **patches** que complementan este comportamiento y corrigen datos históricos en la base de datos:

1. [fix_tipo_dte_from_preinvoice.py](https://github.com/tonicanada/erpnext_chile_factura/blob/main/erpnext_chile_factura/erpnext_chile_sii_integration/patches/fix_tipo_dte_from_preinvoice.py)  
   Corrige el `tipo_dte` en **Purchase Invoice** basándose en la PreInvoice asociada.  

2. [fix_tipo_dte_from_tipo_factura.py](https://github.com/tonicanada/erpnext_chile_factura/blob/main/erpnext_chile_factura/erpnext_chile_sii_integration/patches/fix_tipo_dte_from_tipo_factura.py)  
   Corrige el `tipo_dte` basándose en el valor del campo `tipo_factura` cuando existe.

Estos patches se ejecutan manualmente en el sitio correspondiente con:  

```bash
bench --site <nombre_sitio> execute erpnext_chile_factura.erpnext_chile_sii_integration.patches.fix_tipo_dte_from_preinvoice.execute
bench --site <nombre_sitio> execute erpnext_chile_factura.erpnext_chile_sii_integration.patches.fix_tipo_dte_from_tipo_factura.execute
