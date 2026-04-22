import { Outlet, Navigate } from 'react-router';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';

export function MainLayout() {
  const userJson = localStorage.getItem('user');

  if (!userJson) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen bg-[#F5F5F5]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
