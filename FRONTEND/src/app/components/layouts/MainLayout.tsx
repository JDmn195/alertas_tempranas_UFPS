import { useState } from 'react';
import { Outlet, Navigate } from 'react-router';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { Sheet, SheetContent, SheetTitle } from '../ui/sheet';

export function MainLayout() {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const userJson = localStorage.getItem('user');

  if (!userJson) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Sheet open={menuAbierto} onOpenChange={setMenuAbierto}>
      <div className="flex h-screen bg-[#F5F5F5]">
        <div className="hidden lg:block h-full shrink-0"><Sidebar /></div>
        <SheetContent side="left" className="w-64 max-w-64 p-0 gap-0 lg:hidden">
          <SheetTitle className="sr-only">Menú principal</SheetTitle>
          <Sidebar onNavigate={() => setMenuAbierto(false)} />
        </SheetContent>
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          <TopNav />
          <main className="flex-1 overflow-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </Sheet>
  );
}
