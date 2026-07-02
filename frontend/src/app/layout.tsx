import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoMind CP Portal",
  description: "Channel Partner Dashboard for AutoMind AI Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
