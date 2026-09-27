import type { NavSection } from '@/config/navigation';
import SidebarItem from './SidebarItem';

interface Props {
  section: NavSection;
  collapsed: boolean;
  badges: Record<string, number>;
}

export default function SidebarSection({ section, collapsed, badges }: Props) {
  return (
    <div className="mb-1">
      {collapsed ? (
        <div className="mx-2 my-3 border-t border-white/10" />
      ) : (
        <div className="px-3 pb-1.5 pt-4 text-[10.5px] font-semibold uppercase tracking-wider text-nav-head">
          {section.title}
        </div>
      )}
      <ul className="space-y-0.5">
        {section.items.map((item) => (
          <li key={item.path}>
            <SidebarItem item={item} collapsed={collapsed} badge={item.badgeKey ? badges[item.badgeKey] : undefined} />
          </li>
        ))}
      </ul>
    </div>
  );
}
