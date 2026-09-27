import type { ReactNode } from 'react';
import AppShell from '@/components/layout/AppShell';

// Every page inside the (portal) folder gets the sidebar + navbar.
// The folder name in brackets doesn't appear in the URL.
export default function PortalLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
