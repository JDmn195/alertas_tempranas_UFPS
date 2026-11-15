import type { ElementType, ReactNode } from 'react';
import { AlertCircle, Inbox } from 'lucide-react';

/** Bloque de carga: franjas que laten en lugar de un texto suelto. */
export function CargandoBloque({ texto = 'Cargando…', filas = 4 }: { texto?: string; filas?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3 py-6 px-2">
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="h-4 rounded-md bg-wash animate-pulse" style={{ width: `${92 - i * 11}%` }} />
      ))}
      <span className="sr-only">{texto}</span>
    </div>
  );
}

/** Filas de esqueleto para tablas. */
export function CargandoFilas({ columnas, filas = 5, texto = 'Cargando…' }: { columnas: number; filas?: number; texto?: string }) {
  return (
    <>
      {Array.from({ length: filas }).map((_, i) => (
        <tr key={i} aria-hidden={i > 0}>
          <td colSpan={columnas} className="px-4 py-3">
            <div className="h-4 rounded-md bg-wash animate-pulse" style={{ width: `${96 - (i % 3) * 14}%` }} />
            {i === 0 && <span className="sr-only" role="status">{texto}</span>}
          </td>
        </tr>
      ))}
    </>
  );
}

/** Estado vacío: dice qué pasa y, si se puede, qué hacer. */
export function EstadoVacio({
  titulo,
  detalle,
  icono: Icono = Inbox,
  children,
}: {
  titulo: string;
  detalle?: string;
  icono?: ElementType;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-2 py-12 px-6 animate-in fade-in duration-200">
      <div className="w-12 h-12 rounded-[14px] bg-wash text-ink-muted flex items-center justify-center mb-1">
        <Icono className="w-6 h-6" aria-hidden="true" />
      </div>
      <p className="font-semibold text-ink">{titulo}</p>
      {detalle && <p className="text-sm text-ink-muted max-w-sm">{detalle}</p>}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}

/** Lista de esqueleto con avatar y dos líneas por fila (listas de personas o tarjetas). */
export function CargandoLista({ filas = 4, texto = 'Cargando…' }: { filas?: number; texto?: string }) {
  return (
    <div role="status" aria-live="polite" className="divide-y divide-wash">
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-6 py-5" aria-hidden={i > 0}>
          <div className="w-11 h-11 rounded-[14px] bg-wash animate-pulse shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 rounded-md bg-wash animate-pulse" style={{ width: `${48 - (i % 3) * 8}%` }} />
            <div className="h-3 rounded-md bg-wash animate-pulse" style={{ width: `${30 - (i % 2) * 6}%` }} />
          </div>
        </div>
      ))}
      <span className="sr-only">{texto}</span>
    </div>
  );
}

/** Error con instrucción: qué pasó y qué hacer. */
export function AvisoError({ mensaje, instruccion, children }: { mensaje: string; instruccion?: string; children?: ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-medium">{mensaje}</p>
        {instruccion && <p className="mt-0.5 text-red-700">{instruccion}</p>}
        {children && <div className="mt-2">{children}</div>}
      </div>
    </div>
  );
}
