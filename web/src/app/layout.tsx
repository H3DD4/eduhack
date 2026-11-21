import "@fontsource/noto-sans-arabic/400.css";
import "@fontsource/noto-sans-arabic/700.css";
import "katex/dist/katex.min.css";
import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "ThinkFirst",
  description: "AI that makes you think, not AI that thinks for you.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#F4FBF7" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <head>
        {/* Brand fonts: Acme (all text) and JetBrains Mono (math and code). */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Acme&family=JetBrains+Mono:wght@500&display=swap" />
      </head>
      <body>{children}</body>
    </html>
  );
}
