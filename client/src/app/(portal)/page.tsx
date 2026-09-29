import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import DashboardView from '@/components/dashboard/DashboardView';

export const metadata: Metadata = { title: 'Dashboard' };

export default function Page() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Security operations for today" />
      <DashboardView />
    </>
  );
}
