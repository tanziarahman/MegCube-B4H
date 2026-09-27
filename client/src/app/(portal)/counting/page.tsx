import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'People counting' };

export default function Page() {
  return (
    <>
      <PageHeader title="People counting" subtitle="Occupancy and in / out" />
      <Placeholder text="People counting content goes here" />
    </>
  );
}
