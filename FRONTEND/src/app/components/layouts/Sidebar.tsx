import { useEffect } from 'react';
import { Link, useLocation } from 'react-router';
import {
  BookOpen,
  Upload,
  Users,
  AlertTriangle,
  SlidersHorizontal,
  GraduationCap,
  BarChart3,
  FileDown,
  ShieldCheck,
  LogOut,
  History,
  ClipboardList,
  CalendarClock,
  Home,
  HandHelping,
  Bell,
  CalendarCheck,
  HeartHandshake,
  X,
} from 'lucide-react';
import { cerrarSesionLocal } from '../../../services/session';

export type NavItem = {
  path: string;
  label: string;
  icon: React.ElementType;
  roles?: string[];
  section?: string;
  /** Solo se marca activa en su ruta exacta, no en sus subrutas. */
  exacta?: boolean;
};

export const navItems: NavItem[] = [
  { path: '/dashboard/teacher', label: 'Panel del Docente', icon: GraduationCap, roles: ['DOCENTE'], section: 'Seguimiento' },
  { path: '/dashboard/director', label: 'Panel Estratégico', icon: BarChart3, roles: ['ADMINISTRADOR', 'DIRECTOR'], section: 'Seguimiento' },
  { path: '/dashboard/students', label: 'Estudiantes', icon: Users, roles: ['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE', 'BIENESTAR'], section: 'Seguimiento' },
  { path: '/dashboard/courses', label: 'Cursos', icon: BookOpen, roles: ['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE'], section: 'Seguimiento' },
  { path: '/dashboard/alerts', label: 'Gestión de Alertas', icon: AlertTriangle, roles: ['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR'], section: 'Alertas y apoyo' },
  { path: '/dashboard/solicitudes', label: 'Solicitudes de Acompañamiento', icon: HandHelping, roles: ['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR'], section: 'Alertas y apoyo' },
  { path: '/dashboard/reports', label: 'Exportar Reportes', icon: FileDown, roles: ['ADMINISTRADOR', 'BIENESTAR', 'DOCENTE'], section: 'Alertas y apoyo' },
  { path: '/dashboard/admin/import', label: 'Importar Módulo', icon: Upload, roles: ['ADMINISTRADOR'], section: 'Datos y reglas' },
  { path: '/dashboard/admin/risk-rules', label: 'Reglas de Riesgo', icon: SlidersHorizontal, roles: ['ADMINISTRADOR'], section: 'Datos y reglas' },
  { path: '/dashboard/admin/automatic-processes', label: 'Procesos Automáticos', icon: CalendarClock, roles: ['ADMINISTRADOR', 'DIRECTOR'], section: 'Datos y reglas' },
  { path: '/dashboard/admin/users', label: 'Gestión de Usuarios', icon: ShieldCheck, roles: ['ADMINISTRADOR'], section: 'Accesos y trazabilidad' },
  { path: '/dashboard/admin/notifications-history', label: 'Historial Notif.', icon: History, roles: ['ADMINISTRADOR'], section: 'Accesos y trazabilidad' },
  { path: '/dashboard/admin/audit-log', label: 'Bitácora de Auditoría', icon: ClipboardList, roles: ['ADMINISTRADOR'], section: 'Accesos y trazabilidad' },
  // Portal del estudiante (EP-09): una entrada por sección
  { path: '/dashboard/portal', label: 'Inicio', icon: Home, roles: ['ESTUDIANTE'], section: 'Mi Portal', exacta: true },
  { path: '/dashboard/portal/alertas', label: 'Mis alertas', icon: Bell, roles: ['ESTUDIANTE'], section: 'Mi Portal' },
  { path: '/dashboard/portal/asistencia', label: 'Mi asistencia', icon: CalendarCheck, roles: ['ESTUDIANTE'], section: 'Mi Portal' },
  { path: '/dashboard/portal/acompanamiento', label: 'Mi acompañamiento', icon: HeartHandshake, roles: ['ESTUDIANTE'], section: 'Mi Portal' },
];

// Pantallas que no están en el menú pero tienen nombre propio
const paginasExtra: { patron: RegExp; label: string; section: string }[] = [
  { patron: /^\/dashboard\/students\/[^/]+/, label: 'Perfil del estudiante', section: 'Estudiantes' },
  { patron: /^\/dashboard\/admin\/import-log\//, label: 'Bitácora de importación', section: 'Importar Módulo' },
  { patron: /^\/dashboard\/intervenciones\//, label: 'Evidencias', section: 'Gestión de Alertas' },
  { patron: /^\/dashboard\/notifications/, label: 'Notificaciones', section: 'Avisos' },
];

const nombresDeRol: Record<string, string> = {
  ADMINISTRADOR: 'Administración',
  DIRECTOR: 'Dirección de programa',
  DOCENTE: 'Docente',
  BIENESTAR: 'Bienestar universitario',
  ESTUDIANTE: 'Estudiante',
};

export function nombreDeRol(rol?: string): string {
  return (rol || '').split(',').map((r) => nombresDeRol[r] ?? r).join(', ');
}

export function iniciales(nombre?: string): string {
  const partes = (nombre || '').trim().split(/\s+/).filter(Boolean);
  return ((partes[0]?.[0] ?? '') + (partes[1]?.[0] ?? '')).toUpperCase() || 'U';
}

export function itemsDelRol(rol: string): NavItem[] {
  const roles = rol ? rol.split(',') : [];
  return navItems.filter((item) => !item.roles || item.roles.some((r) => roles.includes(r)));
}

export function estaActivo(item: NavItem, pathname: string): boolean {
  return pathname === item.path || (!item.exacta && pathname.startsWith(item.path + '/'));
}

/** Ubicación actual: sección y nombre de la pantalla (lo usa la barra superior). */
export function ubicacionDePagina(pathname: string): { section?: string; label: string } {
  const extra = paginasExtra.find((p) => p.patron.test(pathname));
  if (extra) return { section: extra.section, label: extra.label };
  const coincide = navItems
    .filter((item) => pathname === item.path || pathname.startsWith(item.path + '/'))
    .sort((a, b) => b.path.length - a.path.length)[0];
  return { section: coincide?.section, label: coincide?.label ?? 'Inicio' };
}

/** Título de la pantalla actual. */
export function tituloDePagina(pathname: string): string {
  return ubicacionDePagina(pathname).label;
}

export function cerrarSesion() {
  cerrarSesionLocal();
  window.location.href = '/login';
}

/**
 * Índice de navegación del personal. No es una caja: vive sobre el fondo del
 * escritorio, junto a la hoja de contenido. En móvil se abre como cajón.
 */
export function Sidebar({ abierto = false, onCerrar = () => {} }: { abierto?: boolean; onCerrar?: () => void }) {
  const location = useLocation();
  const userJson = localStorage.getItem('user');
  const user = userJson ? JSON.parse(userJson) : null;
  const items = itemsDelRol(user?.rol || '');

  const grupos = items.reduce<{ nombre?: string; items: NavItem[] }[]>((acc, item) => {
    const ultimo = acc[acc.length - 1];
    if (ultimo && ultimo.nombre === item.section) ultimo.items.push(item);
    else acc.push({ nombre: item.section, items: [item] });
    return acc;
  }, []);

  useEffect(() => {
    if (!abierto) return;
    const alPresionar = (e: KeyboardEvent) => e.key === 'Escape' && onCerrar();
    window.addEventListener('keydown', alPresionar);
    return () => window.removeEventListener('keydown', alPresionar);
  }, [abierto, onCerrar]);

  return (
    <>
      {abierto && <div className="fixed inset-0 z-30 bg-ink/40 lg:hidden" onClick={onCerrar} aria-hidden="true" />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[17rem] bg-desk h-dvh flex flex-col transition-transform duration-200 lg:static lg:z-auto lg:w-[15.5rem] lg:translate-x-0 lg:shrink-0 ${
          abierto ? 'translate-x-0 shadow-[var(--shadow-pop)]' : '-translate-x-full'
        }`}
        aria-label="Menú principal"
      >
        {/* Identidad */}
        <div className="px-5 pt-5 pb-4 flex items-center justify-between gap-2">
          <Link to="/dashboard" className="flex items-center gap-3 min-w-0 rounded-[10px]">
            <img src="/logo-ufps.svg" alt="Universidad Francisco de Paula Santander" className="h-9 w-auto shrink-0" />
            <span className="min-w-0 border-l border-line-strong pl-3">
              <span className="block text-sm font-semibold text-ink leading-tight whitespace-nowrap">Alertas Tempranas</span>
              <span className="block text-xs text-ink-muted leading-tight mt-0.5 whitespace-nowrap">Seguimiento académico</span>
            </span>
          </Link>
          <button onClick={onCerrar} aria-label="Cerrar menú" className="lg:hidden p-2 rounded-[10px] text-ink-muted hover:bg-wash hover:text-ink">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navegación */}
        <nav className="flex-1 px-3 pb-4 overflow-y-auto">
          {grupos.map((grupo) => (
            <div key={grupo.nombre ?? 'general'} className="mt-4 first:mt-1">
              {grupo.nombre && <p className="px-3 mb-1 text-xs font-medium text-ink-muted">{grupo.nombre}</p>}
              <ul className="space-y-0.5">
                {grupo.items.map((item) => {
                  const Icon = item.icon;
                  const activo = estaActivo(item, location.pathname);
                  return (
                    <li key={item.path}>
                      <Link
                        to={item.path}
                        aria-current={activo ? 'page' : undefined}
                        className={`group flex items-center gap-3 rounded-[10px] px-3 py-2 text-sm ${
                          activo
                            ? 'bg-white text-primary-strong font-semibold shadow-[0_0_0_1px_var(--line),0_1px_2px_rgba(36,26,25,.05)]'
                            : 'text-ink-soft font-medium hover:bg-wash hover:text-ink'
                        }`}
                      >
                        <Icon className={`w-[18px] h-[18px] shrink-0 ${activo ? 'text-primary' : 'text-ink-faint group-hover:text-ink-soft'}`} aria-hidden="true" />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Usuario */}
        <div className="px-3 pb-4">
          <div className="rounded-[10px] border border-line bg-white/70 p-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-primary text-white text-sm font-semibold flex items-center justify-center shrink-0" aria-hidden="true">
                {iniciales(user?.nombre)}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink truncate">{user?.nombre || 'Usuario'}</p>
                <p className="text-xs text-ink-muted truncate">{nombreDeRol(user?.rol)}</p>
              </div>
            </div>
            <button
              onClick={cerrarSesion}
              className="mt-3 w-full flex items-center justify-center gap-2 rounded-[10px] border border-line bg-white px-3 py-2 text-sm font-medium text-ink-soft hover:border-line-strong hover:text-ink"
            >
              <LogOut className="w-4 h-4" aria-hidden="true" />
              Cerrar Sesión
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
