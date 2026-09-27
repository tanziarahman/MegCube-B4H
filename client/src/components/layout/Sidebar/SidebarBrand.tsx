import Link from 'next/link';
import { APP_NAME } from '@/config/navigation';
import { PATHS } from '@/lib/paths';

export default function SidebarBrand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href={PATHS.dashboard} className="flex items-center gap-3 px-2 pb-3 text-white">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-pri text-sm font-bold">B4</span>
      {!collapsed && (
        <span className="leading-tight">
          <span className="block text-sm font-semibold">{APP_NAME}</span>
          <span className="block text-[11px] text-nav-head">Analytics</span>
        </span>
      )}
    </Link>
  );
}
