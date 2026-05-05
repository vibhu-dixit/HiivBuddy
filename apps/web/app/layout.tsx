import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "./auth/AuthProvider";

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
      <body className="min-h-screen antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
