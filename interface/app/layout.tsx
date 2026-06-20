import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "wai",
  description: "wai — Multi-Tenant Agent-Plattform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
