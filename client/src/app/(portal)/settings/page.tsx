import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Settings' };

export default function Page() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Data source and general settings" />
      <Placeholder text="Settings content goes here" />
    </>
  );
}
