// SDAT-346: etiquetas legibles para códigos internos; los valores almacenados no cambian.
const ESTADO_ALERTA: Record<string, string> = {
  activa: 'Activa',
  active: 'Activa',
  en_seguimiento: 'En seguimiento',
  atendida: 'Atendida',
  cerrada: 'Cerrada',
  closed: 'Cerrada',
};

export function etiquetaEstadoAlerta(estado: string | null | undefined): string {
  if (!estado) return '';
  return ESTADO_ALERTA[estado.toLowerCase()] ?? estado.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

const REGLA_CORTE: Record<string, string> = {
  C2A: 'sostenido bajo',
  C2B: 'caída de rendimiento',
  C3: 'nota necesaria alta',
  C4: 'materia perdida',
};

/** «Alerta corte 1», «Alerta corte 2 (sostenido bajo)», «Alerta examen (materia perdida)». */
export function etiquetaAlertaCorte(corte: number | null | undefined, clave: string): string {
  const base = corte ? `Alerta corte ${corte}` : 'Alerta examen';
  return REGLA_CORTE[clave] ? `${base} (${REGLA_CORTE[clave]})` : base;
}
