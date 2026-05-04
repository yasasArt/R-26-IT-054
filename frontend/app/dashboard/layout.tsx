// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg flex">
      {/* Sidebar placeholder — Phase 1 */}
      <aside className="w-56 bg-surface border-r border-card-border flex items-center justify-center">
        <span className="text-text-muted font-mono text-xs">SIDEBAR</span>
      </aside>
      <div className="flex-1 flex flex-col">
        {/* TopBar placeholder — Phase 1 */}
        <header className="h-14 bg-card border-b border-card-border flex items-center px-6">
          <span className="text-text-muted font-mono text-xs">TOP BAR</span>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}