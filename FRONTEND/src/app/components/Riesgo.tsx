/**
 * Lenguaje visual del riesgo, compartido por todo el producto.
 * El nivel se lee por tres vías: color, cantidad de segmentos y texto.
 */
export type NivelRiesgo = 'high' | 'medium' | 'low' | 'unknown';

const NIVELES: Record<NivelRiesgo, { segmentos: number; etiqueta: string; texto: string; fondo: string; borde: string; hex: string }> = {
  high: { segmentos: 4, etiqueta: 'Alto', texto: 'text-red-800', fondo: 'bg-red-50', borde: 'border-red-200', hex: '#B02A2B' },
  medium: { segmentos: 2, etiqueta: 'Medio', texto: 'text-amber-800', fondo: 'bg-amber-50', borde: 'border-amber-200', hex: '#C98A12' },
  low: { segmentos: 1, etiqueta: 'Bajo', texto: 'text-green-800', fondo: 'bg-green-50', borde: 'border-green-200', hex: '#2F8F6B' },
  unknown: { segmentos: 0, etiqueta: 'Sin datos', texto: 'text-ink-muted', fondo: 'bg-wash', borde: 'border-line', hex: '#9C8D8A' },
};

export function normalizarNivel(nivel?: string | null): NivelRiesgo {
  const n = (nivel || '').toString().toLowerCase();
  if (['high', 'alto', 'alta', 'critico', 'crítico'].includes(n)) return 'high';
  if (['medium', 'medio', 'media'].includes(n)) return 'medium';
  if (['low', 'bajo', 'baja'].includes(n)) return 'low';
  return 'unknown';
}

export function colorDeRiesgo(nivel?: string | null): string {
  return NIVELES[normalizarNivel(nivel)].hex;
}

/** Cuatro segmentos que se llenan según el nivel. */
export function MedidorRiesgo({ nivel, className = '' }: { nivel?: string | null; className?: string }) {
  const n = NIVELES[normalizarNivel(nivel)];
  return (
    <span className={`riesgo-medidor ${className}`} data-nivel={n.segmentos} role="img" aria-label={`Riesgo ${n.etiqueta.toLowerCase()}`}>
      <i /><i /><i /><i />
    </span>
  );
}

/** Medidor con su etiqueta; `texto` permite conservar el rótulo propio de cada pantalla. */
export function NivelRiesgoChip({ nivel, texto, className = '' }: { nivel?: string | null; texto?: React.ReactNode; className?: string }) {
  const n = NIVELES[normalizarNivel(nivel)];
  return (
    <span className={`inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs font-semibold ${n.fondo} ${n.borde} ${n.texto} ${className}`}>
      <MedidorRiesgo nivel={nivel} />
      {texto ?? n.etiqueta}
    </span>
  );
}
