import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "./auth/AuthProvider";

import { LANDING_COPY } from "./components/landing/landingCopy";

export const metadata: Metadata = {
  title: LANDING_COPY.meta.title,
  description: LANDING_COPY.meta.description,
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
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
