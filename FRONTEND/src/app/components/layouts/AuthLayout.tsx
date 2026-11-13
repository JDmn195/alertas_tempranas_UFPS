import type { ReactNode } from 'react';
import { MedidorRiesgo } from '../Riesgo';

export const campoAcceso =
  'w-full px-3.5 py-2.5 border border-line-strong rounded-[10px] bg-white text-ink placeholder:text-ink-faint hover:border-ink-faint focus:outline-none focus:ring-[3px] focus:ring-primary/15 focus:border-primary disabled:opacity-50 disabled:bg-paper';

export const etiquetaAcceso = 'block text-sm font-medium text-ink-soft mb-1.5';

const niveles: [string, string, string][] = [
  ['low', 'Riesgo bajo', 'Seguimiento normal'],
  ['medium', 'Riesgo medio', 'Conviene acompañar'],
  ['high', 'Riesgo alto', 'Requiere atención pronta'],
];

/**
 * Marco de las pantallas de acceso: el logo arriba, el mensaje del producto a
 * un lado y el formulario en una hoja blanca. Sin panel oscuro ni imagen.
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh flex flex-col bg-desk">
      <header className="px-5 sm:px-8 lg:px-12 pt-6 flex items-center gap-3">
        <img src="/logo-ufps.svg" alt="Universidad Francisco de Paula Santander" className="h-12 w-auto" />
        <p className="border-l border-line-strong pl-3 text-sm leading-tight">
          <span className="block font-semibold text-ink">Alertas Tempranas</span>
          <span className="block text-ink-muted">Seguimiento académico</span>
        </p>
      </header>

      <div className="flex-1 grid items-center gap-10 lg:gap-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] px-5 sm:px-8 lg:px-12 py-8 mx-auto w-full max-w-6xl">
        <section className="hidden lg:block" aria-label="Sobre el sistema">
          <p className="text-[2.75rem] xl:text-[3.25rem] font-semibold text-ink leading-[1.05] tracking-[-0.03em] max-w-[14ch]">
            Ver a tiempo quién necesita apoyo.
          </p>
          <p className="mt-5 text-lg text-ink-muted max-w-[46ch]">
            Notas, asistencia y riesgo académico en un solo lugar, para actuar antes de que el semestre se complique.
          </p>

          <ul className="mt-10 max-w-md divide-y divide-line border-y border-line" aria-label="Niveles de riesgo">
            {niveles.map(([nivel, nombre, detalle]) => (
              <li key={nivel} className="flex items-center gap-4 py-3">
                <MedidorRiesgo nivel={nivel} />
                <span className="font-semibold text-ink w-28">{nombre}</span>
                <span className="text-sm text-ink-muted">{detalle}</span>
              </li>
            ))}
          </ul>
        </section>

        <main className="w-full max-w-md mx-auto lg:mx-0">
          <div className="bg-white border border-line rounded-[14px] p-6 sm:p-8 shadow-[0_24px_60px_-40px_rgba(36,26,25,.45)]">
            {children}
          </div>
        </main>
      </div>

      <footer className="px-5 sm:px-8 lg:px-12 pb-6 text-xs text-ink-muted">© 2026 Universidad Francisco de Paula Santander</footer>
    </div>
  );
}
