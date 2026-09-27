import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Recognition' };

export default function Page() {
  return (
    <>
      <PageHeader title="Recognition" subtitle="Face matches and strangers" />
      <Placeholder text="Recognition content goes here" />
    </>
  );
}
