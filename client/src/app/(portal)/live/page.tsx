import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Live view' };

export default function Page() {
  return (
    <>
      <PageHeader title="Live view" subtitle="Camera wall and live events" />
      <Placeholder text="Live view content goes here" />
    </>
  );
}
