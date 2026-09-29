import {
  Bell, CalendarClock, Camera, Cpu, LayoutGrid, ScanFace, Settings, TrendingUp, Users, Video, type LucideIcon,
} from 'lucide-react';
import { PATHS } from '@/lib/paths';

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  /** Key used to look up a live count shown as a badge (e.g. new alarms). */
  badgeKey?: 'newAlarms';
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

// Edit this list to add, remove or reorder sidebar links.
export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Monitor',
    items: [
      { label: 'Dashboard', path: PATHS.dashboard, icon: LayoutGrid },
      { label: 'Live view', path: PATHS.live, icon: Video },
    ],
  },
  {
    title: 'Events',
    items: [
      { label: 'Alarms', path: PATHS.alarms, icon: Bell, badgeKey: 'newAlarms' },
      { label: 'Recognition', path: PATHS.recognition, icon: ScanFace },
      { label: 'Captures', path: PATHS.captures, icon: Camera },
      { label: 'People counting', path: PATHS.counting, icon: TrendingUp },
    ],
  },
  {
    title: 'Manage',
    items: [
      { label: 'People', path: PATHS.people, icon: Users },
      { label: 'Devices', path: PATHS.devices, icon: Cpu },
      { label: 'Time plans', path: PATHS.timeplans, icon: CalendarClock },
      { label: 'Settings', path: PATHS.settings, icon: Settings },
    ],
  },
];

export const APP_NAME = 'B4H Portal';
