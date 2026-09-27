import PageHeader from '@/components/common/PageHeader';
import Placeholder from '@/components/common/Placeholder';

export default async function RecognitionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageHeader title={`Recognition ${id}`} subtitle="Recognition detail" />
      <Placeholder text="Recognition detail goes here" />
    </>
  );
}
