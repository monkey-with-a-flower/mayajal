import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mayajal Control Plane",
  description: "Role-aware cyber lab frontend for Mayajal.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
