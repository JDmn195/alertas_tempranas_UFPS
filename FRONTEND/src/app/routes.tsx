import { createBrowserRouter, Navigate } from "react-router";
import { MainLayout } from "./components/layouts/MainLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Login from "./screens/Login";
import ForgotPassword from "./screens/ForgotPassword";
import ResetPassword from "./screens/ResetPassword";
import AdminDashboard from "./screens/AdminDashboard";
import ImportLog from "./screens/ImportLog";
import StudentProfile from "./screens/StudentProfile";
import StudentList from "./screens/StudentList";
import RiskRules from "./screens/RiskRules";
import AlertManagement from "./screens/AlertManagement";
import TeacherDashboard from "./screens/TeacherDashboard";
import DirectorDashboard from "./screens/DirectorDashboard";
import ExportReports from "./screens/ExportReports";
import UserManagement from "./screens/UserManagement";
import CourseList from './screens/CourseList'
import EvidenceManagement from './screens/EvidenceManagement';
import NotificationHistory from "./screens/NotificationHistory";
import NotificationInbox from "./screens/NotificationInbox";
import AuditLog from "./screens/AuditLog";
import AutomaticProcesses from "./screens/AutomaticProcesses";
import StudentPortal from "./screens/StudentPortal";
import SolicitudesAcompanamiento from "./screens/SolicitudesAcompanamiento";
import { PortalLayout } from "./components/layouts/PortalLayout";
import { rutaInicio } from "../services/session";

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
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/forgot-password",
    Component: ForgotPassword,
  },
  {
    path: "/reset-password/:token?",
    Component: ResetPassword,
  },
  {
    path: "/dashboard",
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
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR']}><DirectorDashboard /></ProtectedRoute> 
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
      // Portal del estudiante (EP-09). Las HU-38 a HU-42 agregan aquí sus rutas hijas.
      {
        path: "portal",
        element: <ProtectedRoute allowedRoles={['ESTUDIANTE']}><PortalLayout /></ProtectedRoute>,
        children: [
          { index: true, element: <StudentPortal /> },  // HU-37: riesgo actual
          { path: "*", element: <Navigate to="/dashboard/portal" replace /> },
        ],
      }
    ],
  },
]);
