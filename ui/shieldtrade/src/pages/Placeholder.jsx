export default function Placeholder({ title, subtitle = 'This section is being prepared.' }) {
  return (
    <div className="page-wrap">
      <div className="glass-card h-full flex items-center justify-center p-6">
        <div className="soft-card px-6 py-5 text-center max-w-md">
          <h2 className="title-font text-xl">{title}</h2>
          <p className="text-sm text-[var(--muted)] mt-2">{subtitle}</p>
        </div>
      </div>
    </div>
  );
}
