import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import RecognitionTable from '@/components/recognition/RecognitionTable';

export const metadata: Metadata = { title: 'Recognition' };

export default function Page() {
  return (
    <>
      <PageHeader title="Recognition" subtitle="Face matches and strangers" />
      <RecognitionTable />
    </>
  );
}
