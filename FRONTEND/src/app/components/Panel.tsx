import type { ElementType, ReactNode } from 'react';
import { ArrowUpRight } from 'lucide-react';

/** Encabezado de pantalla: título, una línea de contexto y las acciones a la derecha. */
export function EncabezadoPagina({ titulo, detalle, children }: { titulo: ReactNode; detalle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-[1.65rem] font-semibold text-ink leading-tight tracking-[-0.02em]">{titulo}</h1>
        {detalle && <p className="mt-1 text-ink-muted max-w-[70ch]">{detalle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export type Indicador = {
  etiqueta: string;
  valor: ReactNode;
  detalle?: ReactNode;
  /** Resalta el valor: 'alerta' en rojo, 'aviso' en ámbar, 'bien' en verde. */
  tono?: 'alerta' | 'aviso' | 'bien';
  icono?: ElementType;
  onClick?: () => void;
};

const tonos = { alerta: 'text-riesgo-critico', aviso: 'text-amber-700', bien: 'text-green-700' };

/**
 * Cinta de indicadores: una sola superficie dividida en celdas, en vez de una
 * rejilla de tarjetas sueltas. Las cifras se leen de corrido, como una fila.
 */
export function CintaIndicadores({ indicadores, cargando = false, className = '' }: { indicadores: Indicador[]; cargando?: boolean; className?: string }) {
  return (
    <dl className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-flow-col lg:auto-cols-fr lg:grid-cols-none bg-white border border-line rounded-[14px] overflow-hidden ${className}`}>
      {indicadores.map(({ etiqueta, valor, detalle, tono, onClick }) => {
        const contenido = (
          <>
            <dt className="flex items-start gap-1.5 text-sm font-medium text-ink-muted w-full">
              <span>{etiqueta}</span>
              {onClick && <ArrowUpRight className="w-4 h-4 ml-auto mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />}
            </dt>
            <dd className="mt-2">
              {cargando ? (
                <span className="block w-14 h-8 rounded-md bg-wash animate-pulse" />
              ) : (
                <span className={`cifra block text-[1.75rem] font-semibold leading-none tracking-[-0.02em] ${tono ? tonos[tono] : 'text-ink'}`}>{valor}</span>
              )}
              {detalle && <span className="block mt-1.5 text-xs text-ink-muted">{detalle}</span>}
            </dd>
          </>
        );
        const celda = 'flex flex-col justify-start text-left px-4 py-4 sm:px-5 border-line -mb-px -mr-px border-b border-r';
        return onClick ? (
          <button key={etiqueta} type="button" onClick={onClick} disabled={cargando} className={`${celda} hover:bg-paper`}>
            {contenido}
          </button>
        ) : (
          <div key={etiqueta} className={celda}>
            {contenido}
          </div>
        );
      })}
    </dl>
  );
}

/** Sección con título, para agrupar contenido dentro de una pantalla. */
export function Seccion({
  titulo,
  detalle,
  accion,
  children,
  className = '',
  sinRelleno = false,
}: {
  titulo: ReactNode;
  detalle?: ReactNode;
  accion?: ReactNode;
  children: ReactNode;
  className?: string;
  sinRelleno?: boolean;
}) {
  return (
    <section className={`bg-white border border-line rounded-[14px] ${className}`}>
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">{titulo}</h2>
          {detalle && <p className="text-sm text-ink-muted mt-0.5">{detalle}</p>}
        </div>
        {accion}
      </header>
      <div className={sinRelleno ? '' : 'px-5 pb-5'}>{children}</div>
    </section>
  );
}

export type Tramo = { etiqueta: string; valor: number; color: string };

/**
 * Barra de distribución: muestra las partes de un total en una sola franja.
 * Cada tramo tiene su cifra en la leyenda, así no depende solo del color.
 */
export function BarraDistribucion({ tramos, unidad = '' }: { tramos: Tramo[]; unidad?: string }) {
  const total = tramos.reduce((s, t) => s + t.valor, 0);
  return (
    <div>
      <div className="flex h-3 gap-0.5 rounded-full overflow-hidden bg-wash" role="img" aria-label={tramos.map((t) => `${t.etiqueta}: ${t.valor}`).join(', ')}>
        {total > 0 && tramos.filter((t) => t.valor > 0).map((t) => (
          <span key={t.etiqueta} style={{ width: `${(t.valor / total) * 100}%`, background: t.color }} />
        ))}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
        {tramos.map((t) => (
          <li key={t.etiqueta} className="min-w-0">
            <p className="flex items-center gap-1.5 text-sm text-ink-muted">
              <span className="w-2.5 h-2.5 rounded-[3px] shrink-0" style={{ background: t.color }} aria-hidden="true" />
              <span>{t.etiqueta}</span>
            </p>
            <p className="cifra mt-1 text-xl font-semibold text-ink leading-none">
              {t.valor}
              {unidad && <span className="text-sm font-medium text-ink-muted"> {unidad}</span>}
              {total > 0 && <span className="ml-2 text-sm font-medium text-ink-muted">{Math.round((t.valor / total) * 100)}%</span>}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
