// Utilidades de presentación: solo formatean al mostrar, nunca modifican datos.

const ZONA = 'America/Bogota';

function aFecha(valor: string | Date | null | undefined): Date | null {
  if (!valor) return null;
  // Una fecha sin hora (YYYY-MM-DD) se interpreta como local para no correrla un día
  const f = typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor)
    ? new Date(`${valor}T00:00:00`)
    : new Date(valor);
  return Number.isNaN(f.getTime()) ? null : f;
}

/** Fecha corta: «16 nov 2026». */
export function formatearFecha(valor: string | Date | null | undefined): string {
  const f = aFecha(valor);
  return f ? f.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: ZONA }) : '—';
}

/** Fecha y hora (hora de Colombia): «16 nov 2026, 2:00 a. m.». */
export function formatearFechaHora(valor: string | Date | null | undefined): string {
  const f = aFecha(valor);
  return f
    ? f.toLocaleString('es-CO', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: ZONA })
    : '—';
}

const MINUSCULAS = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y', 'e', 'o', 'en', 'a', 'al', 'para', 'con', 'por']);
const ROMANOS = /^(i|ii|iii|iv|v|vi|vii|viii|ix|x)$/i;

/** Nombre de materia legible: «TEORIA GENERAL DE LAS COMUNICA» -> «Teoria General de las Comunica». */
export function normalizarNombreMateria(nombre: string | null | undefined): string {
  if (!nombre) return '';
  return nombre
    .trim()
    .replace(/\s+/g, ' ')
    .split(' ')
    .map((p, i) => {
      const bajo = p.toLowerCase();
      if (ROMANOS.test(p)) return p.toUpperCase();
      if (i > 0 && MINUSCULAS.has(bajo)) return bajo;
      return bajo.charAt(0).toUpperCase() + bajo.slice(1);
    })
    .join(' ');
}

/** Código sin el «.0» que dejan algunas importaciones: «1155501.0» -> «1155501». */
export function normalizarCodigo(codigo: string | number | null | undefined): string {
  if (codigo === null || codigo === undefined) return '';
  return String(codigo).trim().replace(/\.0+$/, '');
}
