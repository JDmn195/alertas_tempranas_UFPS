import { useEffect, useRef, useState } from 'react';
import { Outlet, Navigate, Link, useLocation } from 'react-router';
import { LogOut } from 'lucide-react';
import { Sidebar, cerrarSesion, estaActivo, iniciales, itemsDelRol } from './Sidebar';
import { TopNav } from './TopNav';

const enlaceSalto =
  'sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:bg-white focus:text-primary focus:px-4 focus:py-2 focus:rounded-[10px] focus:shadow-lg';

export function MainLayout() {
  const userJson = localStorage.getItem('user');
  const location = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const contenido = useRef<HTMLElement>(null);

  // Al cambiar de pantalla se cierra el menú móvil y se vuelve arriba
  useEffect(() => {
    setMenuAbierto(false);
    contenido.current?.scrollTo({ top: 0 });
  }, [location.pathname]);

  if (!userJson) {
    return <Navigate to="/login" replace />;
  }

  let user: { nombre?: string; rol?: string } | null = null;
  try { user = JSON.parse(userJson); } catch { user = null; }

  if (user?.rol === 'ESTUDIANTE') {
    return <EstructuraPortal nombre={user.nombre} contenido={contenido} pathname={location.pathname} />;
  }

  // Personal: índice sobre el escritorio y una hoja de trabajo a la derecha
  return (
    <div className="flex h-dvh bg-desk">
      <a href="#contenido" className={enlaceSalto}>Saltar al contenido</a>
      <Sidebar abierto={menuAbierto} onCerrar={() => setMenuAbierto(false)} />
      <div className="flex-1 flex flex-col min-w-0 bg-[#FBF3F1] lg:my-2 lg:mr-2 lg:rounded-[14px] lg:border lg:border-line overflow-hidden">
        <TopNav onMenu={() => setMenuAbierto(true)} />
        <main id="contenido" ref={contenido} className="flex-1 overflow-auto px-3 py-5 sm:px-5 lg:px-7 lg:py-6">
          <div key={location.pathname} className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

/**
 * Portal del estudiante: sin menú lateral. Cuatro secciones en pestañas arriba
 * (abajo en el teléfono) y una columna de lectura centrada.
 */
function EstructuraPortal({ nombre, contenido, pathname }: { nombre?: string; contenido: React.RefObject<HTMLElement | null>; pathname: string }) {
  const items = itemsDelRol('ESTUDIANTE');

  return (
    <div className="flex flex-col h-dvh bg-[#F8ECE9]">
      <a href="#contenido" className={enlaceSalto}>Saltar al contenido</a>
      <header className="shrink-0 bg-white border-b border-line">
        <div className="mx-auto max-w-6xl h-16 px-4 sm:px-6 flex items-center justify-between gap-4">
          <Link to="/dashboard/portal" className="flex items-center gap-3 min-w-0 rounded-[10px]">
            <img src="/logo-ufps.svg" alt="Universidad Francisco de Paula Santander" className="h-9 w-auto shrink-0" />
            <span className="hidden xl:block border-l border-line-strong pl-3 text-sm font-semibold text-ink leading-tight whitespace-nowrap">Mi seguimiento académico</span>
          </Link>

          <nav className="hidden md:flex items-center gap-1" aria-label="Secciones del portal">
            {items.map((item) => {
              const activo = estaActivo(item, pathname);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  aria-current={activo ? 'page' : undefined}
                  className={`rounded-full px-3.5 py-2 text-sm font-medium whitespace-nowrap ${
                    activo ? 'bg-primary text-white' : 'text-ink-soft hover:bg-wash hover:text-ink'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2 shrink-0">
            <div className="hidden sm:flex items-center gap-2 pr-1">
              <span className="w-8 h-8 rounded-full bg-primary-tint text-primary-strong text-xs font-semibold flex items-center justify-center" aria-hidden="true">
                {iniciales(nombre)}
              </span>
              <span className="hidden lg:block text-sm font-medium text-ink max-w-40 truncate">{nombre}</span>
            </div>
            <button
              onClick={cerrarSesion}
              className="flex items-center gap-2 rounded-full border border-line px-3 py-2 text-sm font-medium text-ink-soft hover:border-line-strong hover:text-ink"
            >
              <LogOut className="w-4 h-4" aria-hidden="true" />
              <span className="max-sm:sr-only">Cerrar Sesión</span>
            </button>
          </div>
        </div>
      </header>

      <main id="contenido" ref={contenido} className="portal flex-1 overflow-auto">
        <div key={pathname} className="page-enter mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-8 pb-24 md:pb-10">
          <Outlet />
        </div>
      </main>

      {/* Teléfono: las cuatro secciones quedan al alcance del pulgar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-line grid grid-cols-4 pb-[env(safe-area-inset-bottom)]" aria-label="Secciones del portal">
        {items.map((item) => {
          const Icon = item.icon;
          const activo = estaActivo(item, pathname);
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={activo ? 'page' : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 px-1 text-[11px] font-medium min-w-0 ${activo ? 'text-primary' : 'text-ink-muted'}`}
            >
              <span className={`flex items-center justify-center w-12 h-7 rounded-full ${activo ? 'bg-primary-tint' : ''}`}>
                <Icon className="w-[18px] h-[18px]" aria-hidden="true" />
              </span>
              <span className="max-w-full truncate">{item.label.replace(/^Mis? /, '').replace(/^./, (c) => c.toUpperCase()).replace('Acompañamiento', 'Apoyo')}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
