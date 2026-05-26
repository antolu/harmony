export function ChatSidebar({ collapsed }: { collapsed: boolean }) {
  return <aside className={collapsed ? "w-12" : "w-64"} />;
}
