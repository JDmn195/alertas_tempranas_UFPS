import { createBrowserRouter, Navigate } from "react-router";
import { lazy, Suspense, type ComponentType } from "react";
import { MainLayout } from "./components/layouts/MainLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Login from "./screens/Login";
import ForgotPassword from "./screens/ForgotPassword";
import ResetPassword from "./screens/ResetPassword";
import NotFound from "./screens/NotFound";
import ErrorRuta from "./screens/ErrorRuta";
import { PortalLayout } from "./components/layouts/PortalLayout";
import { rutaInicio } from "../services/session";

// SDAT-315: cada pantalla se descarga al abrir su ruta.
function pantallaDiferida(cargar: () => Promise<{ default: ComponentType }>) {
  const Pantalla = lazy(cargar);
  return function PantallaConEspera() {
    return <Suspense fallback={<p role="status" className="p-6">Cargando pantalla…</p>}><Pantalla /></Suspense>;
  };
}

const AdminDashboard = pantallaDiferida(() => import('./screens/AdminDashboard'));
const ImportLog = pantallaDiferida(() => import('./screens/ImportLog'));
const StudentProfile = pantallaDiferida(() => import('./screens/StudentProfile'));
const StudentList = pantallaDiferida(() => import('./screens/StudentList'));
const RiskRules = pantallaDiferida(() => import('./screens/RiskRules'));
const AlertManagement = pantallaDiferida(() => import('./screens/AlertManagement'));
const TeacherDashboard = pantallaDiferida(() => import('./screens/TeacherDashboard'));
const DirectorDashboard = pantallaDiferida(() => import('./screens/DirectorDashboard'));
const ExportReports = pantallaDiferida(() => import('./screens/ExportReports'));
const UserManagement = pantallaDiferida(() => import('./screens/UserManagement'));
const CourseList = pantallaDiferida(() => import('./screens/CourseList'));
const EvidenceManagement = pantallaDiferida(() => import('./screens/EvidenceManagement'));
const NotificationHistory = pantallaDiferida(() => import('./screens/NotificationHistory'));
const NotificationInbox = pantallaDiferida(() => import('./screens/NotificationInbox'));
const AuditLog = pantallaDiferida(() => import('./screens/AuditLog'));
const AutomaticProcesses = pantallaDiferida(() => import('./screens/AutomaticProcesses'));
const SolicitudesAcompanamiento = pantallaDiferida(() => import('./screens/SolicitudesAcompanamiento'));
const StudentPortal = pantallaDiferida(() => import('./screens/StudentPortal'));
const PortalAcompanamiento = pantallaDiferida(() => import('./screens/StudentPortal').then(m => ({ default: m.PortalAcompanamiento })));
const PortalAlertas = pantallaDiferida(() => import('./screens/StudentPortal').then(m => ({ default: m.PortalAlertas })));
const PortalAsistencia = pantallaDiferida(() => import('./screens/StudentPortal').then(m => ({ default: m.PortalAsistencia })));
const Ayuda = pantallaDiferida(() => import('./screens/Ayuda'));

// Pantalla inicial de /dashboard según el rol (el estudiante va a su portal)
function InicioDashboard() {
  let rol: string | undefined;
  try {
    rol = JSON.parse(localStorage.getItem('user') || 'null')?.rol;
  } catch {
    rol = undefined;
  }
  return <Navigate to={rutaInicio(rol)} replace />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Login,
    errorElement: <ErrorRuta />,
  },
  {
    path: "/login",
    Component: Login,
    errorElement: <ErrorRuta />,
  },
  {
    path: "/forgot-password",
    Component: ForgotPassword,
    errorElement: <ErrorRuta />,
  },
  {
    path: "/reset-password/:token?",
    Component: ResetPassword,
    errorElement: <ErrorRuta />,
  },
  {
    path: "/dashboard",
    errorElement: <ErrorRuta />,
    element: (
      <ProtectedRoute>
        <MainLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <InicioDashboard /> },
      { 
        path: "admin/import", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><AdminDashboard /></ProtectedRoute> 
      },
      { 
        path: "admin/import-log/:id", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><ImportLog /></ProtectedRoute> 
      },
      { 
        path: "admin/risk-rules", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><RiskRules /></ProtectedRoute> 
      },
      { 
        path: "admin/users", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><UserManagement /></ProtectedRoute> 
      },
      { 
        path: "admin/audit-log", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><AuditLog /></ProtectedRoute> 
      },
      { 
        path: "students", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE', 'BIENESTAR']}><StudentList /></ProtectedRoute> 
      },
      { 
        path: "students/:id", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE', 'BIENESTAR']}><StudentProfile /></ProtectedRoute> 
      },
      { 
        path: "alerts", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR']}><AlertManagement /></ProtectedRoute> 
      },
      {
        path: "intervenciones/:intervencionId/evidencias",
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR']}><EvidenceManagement /></ProtectedRoute>
      },
      { 
        path: "teacher", 
        element: <ProtectedRoute allowedRoles={['DOCENTE']}><TeacherDashboard /></ProtectedRoute> 
      },
      { 
        path: "director", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR']}><DirectorDashboard /></ProtectedRoute> 
      },
      { 
        path: "reports", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'BIENESTAR', 'DOCENTE']}><ExportReports /></ProtectedRoute> 
      },
      { 
        path: "courses", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE']}><CourseList /></ProtectedRoute> 
      },
      {
        path: "notifications",
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'DIRECTOR', 'BIENESTAR']}><NotificationInbox /></ProtectedRoute>
      },
      {
        // HU-41: bandeja de solicitudes de acompañamiento de los estudiantes
        path: "solicitudes",
        element: <ProtectedRoute allowedRoles={['BIENESTAR', 'DIRECTOR', 'ADMINISTRADOR']}><SolicitudesAcompanamiento /></ProtectedRoute>
      },
      {
        path: "admin/automatic-processes",
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR']}><AutomaticProcesses /></ProtectedRoute>
      },
      {
        path: "admin/notifications-history",
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><NotificationHistory /></ProtectedRoute>
      },
      { path: "ayuda", element: <Ayuda /> },
      // Portal del estudiante (EP-09): una ruta por sección de la barra lateral
      {
        path: "portal",
        element: <ProtectedRoute allowedRoles={['ESTUDIANTE']}><PortalLayout /></ProtectedRoute>,
        children: [
          { index: true, element: <StudentPortal /> },  // Inicio: riesgo (HU-37) y evolución (HU-38)
          { path: "alertas", element: <PortalAlertas /> },  // HU-39
          { path: "asistencia", element: <PortalAsistencia /> },  // HU-42
          { path: "acompanamiento", element: <PortalAcompanamiento /> },  // HU-40 y HU-41
          { path: "*", element: <Navigate to="/dashboard/portal" replace /> },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
  { path: "*", element: <NotFound />, errorElement: <ErrorRuta /> },
]);
