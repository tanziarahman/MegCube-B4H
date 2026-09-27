import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export const metadata: Metadata = { title: 'Captures' };

export default function Page() {
  return (
    <>
      <PageHeader title="Captures" subtitle="Faces, people, vehicles and plates" />
      <Placeholder text="Captures content goes here" />
    </>
  );
}
