import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import DevicesTable from '@/components/devices/DevicesTable';

export const metadata: Metadata = { title: 'Devices' };

export default function Page() {
  return (
    <>
      <PageHeader title="Devices" subtitle="Cameras connected to the box" />
      <DevicesTable />
    </>
  );
}