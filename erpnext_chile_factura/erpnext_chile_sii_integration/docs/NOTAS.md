# Notas Técnicas - Client Script Autocompletar tipo_dte

## Descripción

Este Client Script autocompleta el campo `tipo_dte` en el Doctype **Purchase Invoice** a partir del valor del campo `tipo_factura`.

## Consideraciones

- Este campo `tipo_factura` **no es estándar en ERPNext**, por lo que el script verifica si existe antes de actuar.
- Está pensado principalmente para la empresa Constructora Tecton, donde se añadió dicho campo.
- Si la empresa no tiene este campo, el script no realiza ninguna acción, manteniendo la compatibilidad.
- Esta implementación permite que la app sea reusable y segura en entornos con o sin `tipo_factura`.

## Uso

- El script está incluido como fixture en la app y se instala automáticamente.
- El comportamiento se activa solo en formularios que contengan el campo `tipo_factura`.

## Autor

Antonio Cañada Momblant
