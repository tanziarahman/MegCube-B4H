import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import PeopleView from '@/components/people/PeopleView';

export const metadata: Metadata = { title: 'People' };

export default function Page() {
  return (
    <>
      <PageHeader title="People" subtitle="Face library and groups" />
      <PeopleView />
    </>
  );
}
