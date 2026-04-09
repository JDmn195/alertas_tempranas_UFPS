import { createBrowserRouter } from "react-router";
import { MainLayout } from "./components/layouts/MainLayout";
import Login from "./screens/Login";
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
    path: "/dashboard",
    Component: MainLayout,
    children: [
      { index: true, Component: AdminDashboard },
      { path: "admin/import", Component: AdminDashboard },
      { path: "admin/import-log/:id", Component: ImportLog },
      { path: "admin/risk-rules", Component: RiskRules },
      { path: "admin/users", Component: UserManagement },
      { path: "students", Component: StudentList },
      { path: "students/:id", Component: StudentProfile },
      { path: "alerts", Component: AlertManagement },
      { path: "teacher", Component: TeacherDashboard },
      { path: "director", Component: DirectorDashboard },
      { path: "reports", Component: ExportReports },
    ],
  },
]);
