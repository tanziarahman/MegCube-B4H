import DevicesTable from './DevicesTable';

export const metadata = { title: 'Devices · B4H Portal' };

export default function DevicesPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[20px] font-semibold">Devices</h1>
        <p className="mt-1 text-[13px] text-mute">Cameras connected to the box</p>
      </div>
      <DevicesTable />
    </div>
  );
}
