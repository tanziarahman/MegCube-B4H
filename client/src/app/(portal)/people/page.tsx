import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'People' };

export default function Page() {
  return (
    <>
      <PageHeader title="People" subtitle="Face library and groups" />
      <Placeholder text="People content goes here" />
    </>
  );
}
