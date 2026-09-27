import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export default async function AlarmDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageHeader title={`Alarm ${id}`} subtitle="Alarm detail" />
      <Placeholder text="Alarm detail goes here" />
    </>
  );
}
