import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Devices' };

export default function Page() {
  return (
    <>
      <PageHeader title="Devices" subtitle="Boxes and cameras" />
      <Placeholder text="Devices content goes here" />
    </>
  );
}
