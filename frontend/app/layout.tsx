import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Vision System | Apparel Manufacturing",
  description:
    "Local workstation dashboard for AI-powered apparel manufacturing monitoring",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const themeScript = `
    try {
      const saved = localStorage.getItem("ai-vision-theme");
      const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
      if (saved === "light" || (!saved && prefersLight)) document.documentElement.classList.add("light");
    } catch {}
  `;

  return (
    <html lang="en" suppressHydrationWarning className={`${spaceGrotesk.variable} ${ibmPlexMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <div className="app-root">{children}</div>
      </body>
    </html>
  );
}
