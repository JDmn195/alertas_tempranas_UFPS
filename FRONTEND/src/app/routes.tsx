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
      { index: true, element: <Navigate to="students" replace /> },
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
        path: "students", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR']}><StudentList /></ProtectedRoute> 
      },
      { 
        path: "students/:id", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR']}><StudentProfile /></ProtectedRoute> 
      },
      { 
        path: "alerts", 
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR']}><AlertManagement /></ProtectedRoute> 
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
        element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'BIENESTAR']}><ExportReports /></ProtectedRoute> 
      },
      { path: 'courses', element: <ProtectedRoute allowedRoles={['ADMINISTRADOR', 'DIRECTOR', 'DOCENTE']}><CourseList /></ProtectedRoute> 
}
    ],
  },
]);
