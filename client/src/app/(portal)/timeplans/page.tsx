import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import TimeplansView from '@/components/timeplans/TimeplansView';

export const metadata: Metadata = { title: 'Time plans' };

export default function TimeplansPage() {
  return (
    <>
      <PageHeader title="Time plans" subtitle="Shape when your security rules are active" />
      <TimeplansView />
    </>
  );
}