import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import CapturesView from '@/components/captures/CapturesView';

export const metadata: Metadata = { title: 'Captures' };

export default function Page() {
  return (
    <>
      <PageHeader title="Captures" subtitle="Faces, people, vehicles and plates" />
      <CapturesView />
    </>
  );
}