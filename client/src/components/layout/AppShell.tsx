'use client';

import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import { useLocalStorage } from '@/hooks/useLocalStorage';

/** Shell for every signed-in page: sidebar on the left, navbar on top, page below. */
export default function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useLocalStorage('sidebar-collapsed', false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar onToggleSidebar={() => setCollapsed((c) => !c)} sidebarCollapsed={collapsed} />
        <main className="flex-1 overflow-y-auto px-6 py-5">{children}</main>
      </div>
    </div>
  );
}
