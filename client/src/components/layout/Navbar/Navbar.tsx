'use client';

import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import SearchBox from './SearchBox';
import StatusIndicators from './StatusIndicators';
import LanguageSwitch from './LanguageSwitch';
import UserMenu from './UserMenu';

interface NavbarProps {
  onToggleSidebar: () => void;
  sidebarCollapsed: boolean;
}

export default function Navbar({ onToggleSidebar, sidebarCollapsed }: NavbarProps) {
  const ToggleIcon = sidebarCollapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-white px-5">
      <button
        type="button"
        onClick={onToggleSidebar}
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="rounded-md p-1.5 text-mute hover:bg-ground hover:text-ink"
      >
        <ToggleIcon size={19} />
      </button>
      <SearchBox />
      <div className="ml-auto flex items-center gap-4">
        <StatusIndicators />
        <LanguageSwitch />
        <UserMenu />
      </div>
    </header>
  );
}
