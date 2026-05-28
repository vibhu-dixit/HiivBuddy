/** Avoid serving a stale static shell; Decision Room must pick up UI changes after edits. */
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function DecisionRoomLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="decision-room-shell flex h-[100dvh] max-h-[100dvh] min-h-0 flex-col overflow-hidden bg-[var(--background)]">
      {children}
    </div>
  );
}
