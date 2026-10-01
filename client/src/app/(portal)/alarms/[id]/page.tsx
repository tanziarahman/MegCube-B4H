import type { Metadata } from 'next';
import PageHeader from '@/components/common/PageHeader';
import IncidentDetail from '@/components/alarms/IncidentDetail';

export const metadata: Metadata = { title: 'Alarm' };

// `id` is the alarm number, or the public id used in alarm emails.
export default async function AlarmDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageHeader title="Alarm" subtitle="What was detected, and who was told" />
      <IncidentDetail incidentRef={id} />
    </>
  );
}
