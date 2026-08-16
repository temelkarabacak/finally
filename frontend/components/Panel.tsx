interface PanelProps {
  label: string;
  /** Short annotation shown beside the label, e.g. a count or unit. */
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}

export function Panel({ label, meta, actions, className = "", bodyClassName = "", children }: PanelProps) {
  return (
    <section
      className={`flex min-h-0 flex-col overflow-hidden rounded-sm border border-edge bg-panel ${className}`}
    >
      <header className="flex h-8 shrink-0 items-center gap-3 border-b border-edge bg-panel-head px-3">
        <h2 className="panel-label shrink-0">{label}</h2>
        {meta ? (
          <span className="num truncate text-[10px] whitespace-nowrap text-ink-muted">{meta}</span>
        ) : null}
        <div className="ml-auto flex shrink-0 items-center gap-2">{actions}</div>
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
