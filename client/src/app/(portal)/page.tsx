import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Dashboard' };

export default function Page() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Today at a glance" />
      <Placeholder text="Dashboard content goes here" />
    </>
  );
}
