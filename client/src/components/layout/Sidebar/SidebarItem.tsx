'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { NavItem } from '@/config/navigation';
import { PATHS } from '@/lib/paths';

interface Props {
  item: NavItem;
  collapsed: boolean;
  badge?: number;
}

export default function SidebarItem({ item, collapsed, badge }: Props) {
  const pathname = usePathname();
  const Icon = item.icon;
  // Dashboard ("/") matches exactly; other items also match their sub-pages (e.g. /alarms/123).
  const isActive =
    item.path === PATHS.dashboard ? pathname === item.path : pathname === item.path || pathname.startsWith(`${item.path}/`);

  return (
    <Link
      href={item.path}
      title={collapsed ? item.label : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={`relative flex h-9 items-center gap-3 rounded-md px-3 text-[13px] transition-colors ${
        isActive ? 'bg-nav-active font-medium text-white' : 'text-nav-text hover:bg-nav-hover hover:text-white'
      } ${collapsed ? 'justify-center px-0' : ''}`}
    >
      <Icon size={17} strokeWidth={1.8} aria-hidden />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {badge !== undefined && badge > 0 && (
        <span
          className={`rounded-full bg-crit text-[10.5px] font-semibold text-white ${
            collapsed ? 'absolute right-1 top-1 h-2 w-2' : 'ml-auto px-1.5 py-px'
          }`}
          aria-label={`${badge} new`}
        >
          {!collapsed && badge}
        </span>
      )}
    </Link>
  );
}
