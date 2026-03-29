import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HiivBuddy — Decision Room",
  description: "Swarm-style AI debate for decisions",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
