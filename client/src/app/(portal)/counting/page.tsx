import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import CountingView from '@/components/counting/CountingView';

export const metadata: Metadata = { title: 'People counting' };

export default function Page() {
  return (
    <>
      <PageHeader title="People counting" subtitle="Walk-pasts and different people per camera" />
      <CountingView />
    </>
  );
}
