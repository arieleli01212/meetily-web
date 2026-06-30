import "./globals.css";
import type { Metadata } from "next";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Meetily Web",
  description: "Privacy-first, air-gapped AI meeting assistant (web edition)",
};

// Applies the saved theme before first paint to avoid a flash of the wrong
// theme. Falls back to the OS preference. Runs inline, fully offline.
const themeBoot = `(function(){try{var t=localStorage.getItem('meetily-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body>
        <NavBar />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
