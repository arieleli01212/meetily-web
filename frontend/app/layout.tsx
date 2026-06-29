import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Meetily Web",
  description: "Privacy-first, air-gapped AI meeting assistant (web edition)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <Link href="/" className="brand">
            Meetily Web
          </Link>
          <Link href="/" className="link">
            Meetings
          </Link>
          <Link href="/record" className="link">
            Record
          </Link>
          <Link href="/settings" className="link">
            Settings
          </Link>
        </nav>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
