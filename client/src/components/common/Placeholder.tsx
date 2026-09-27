/** Temporary block shown until a page's real content is built. */
export default function Placeholder({ text }: { text: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-line bg-white text-sm text-mute">
      {text}
    </div>
  );
}
