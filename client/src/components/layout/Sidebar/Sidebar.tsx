'use client';

import { NAV_SECTIONS } from '@/config/navigation';
import { useOpenAlarmCount } from '@/hooks/useOpenAlarmCount';
import SidebarBrand from './SidebarBrand';
import SidebarSection from './SidebarSection';

interface SidebarProps {
  collapsed: boolean;
}

export default function Sidebar({ collapsed }: SidebarProps) {
  const badges = { newAlarms: useOpenAlarmCount() };

  return (
    <nav
      aria-label="Main"
      className={`flex shrink-0 flex-col bg-nav py-3 transition-[width] duration-200 ${
        collapsed ? 'w-16 px-2' : 'w-[232px] px-3'
      }`}
    >
      <SidebarBrand collapsed={collapsed} />
      <div className="mt-2 flex-1 overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <SidebarSection key={section.title} section={section} collapsed={collapsed} badges={badges} />
        ))}
      </div>
      {!collapsed && <div className="border-t border-white/5 px-2 pt-3 text-[11px] text-nav-head">v0.1 · demo</div>}
    </nav>
  );
}
