import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GemPilot — full-stack hackathon project generator",
  description:
    "Describe your hackathon idea, connect GitHub, and let configurable AI agents plan, build, validate, demo-package, and export a full-stack project repository.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
