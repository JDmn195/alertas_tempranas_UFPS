/**
 * Copia el texto de cada encabezado a `data-label` de las celdas de su columna,
 * para que `.tabla-tarjetas` pueda mostrarlo en la vista de tarjetas (bajo `md`).
 */
export function etiquetarTablas(raiz: HTMLElement) {
  raiz.querySelectorAll<HTMLTableElement>('table.tabla-tarjetas').forEach((tabla) => {
    const etiquetas = Array.from(tabla.tHead?.rows[0]?.cells ?? []).map((th) => (th.textContent || '').trim());
    Array.from(tabla.tBodies).flatMap((cuerpo) => Array.from(cuerpo.rows)).forEach((fila) => {
      Array.from(fila.children).forEach((celda, i) => {
        if (!(celda instanceof HTMLTableCellElement) || celda.colSpan > 1) return;
        const etiqueta = etiquetas[i] ?? '';
        if (celda.getAttribute('data-label') !== etiqueta) {
          if (etiqueta) celda.setAttribute('data-label', etiqueta);
          else celda.removeAttribute('data-label');
        }
      });
    });
  });
}
