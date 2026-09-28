import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import LiveView from './LiveView';

export const metadata: Metadata = { title: 'Live view' };

export default function Page() {
  return (
    <>
      <PageHeader title="Live view" subtitle="Camera wall and latest recognitions" />
      <LiveView />
    </>
  );
}