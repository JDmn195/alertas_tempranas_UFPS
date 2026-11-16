// SDAT-341: navegación simple para listados paginados en servidor.
interface PaginacionProps {
  pagina: number;
  paginas: number;
  total: number;
  onCambio: (pagina: number) => void;
}

export function Paginacion({ pagina, paginas, total, onCambio }: PaginacionProps) {
  if (paginas <= 1) return null;
  const boton = 'h-9 px-3 text-sm rounded-[10px] border border-line-strong bg-white text-ink disabled:opacity-50';
  return (
    <nav aria-label="Paginación" className="flex items-center justify-between gap-3 px-5 py-3 border-t border-line text-sm text-ink-muted">
      <span>Página {pagina} de {paginas} · {total} registros</span>
      <div className="flex gap-2">
        <button type="button" className={boton} disabled={pagina <= 1} onClick={() => onCambio(pagina - 1)}>Anterior</button>
        <button type="button" className={boton} disabled={pagina >= paginas} onClick={() => onCambio(pagina + 1)}>Siguiente</button>
      </div>
    </nav>
  );
}
