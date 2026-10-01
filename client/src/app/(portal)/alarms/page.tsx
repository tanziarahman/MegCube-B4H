import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import AlarmsView from '@/components/alarms/AlarmsView';

export const metadata: Metadata = { title: 'Alarms' };

export default function Page() {
  return (
    <>
      <PageHeader title="Alarms" subtitle="Your own rules, checked against every detection from the box" />
      <AlarmsView />
    </>
  );
}
