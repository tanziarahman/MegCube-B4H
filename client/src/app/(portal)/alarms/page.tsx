import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Alarms' };

export default function Page() {
  return (
    <>
      <PageHeader title="Alarms" subtitle="Rule-based alarms reported by the boxes" />
      <Placeholder text="Alarms content goes here" />
    </>
  );
}
