import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Inter } from "next/font/google";
import { ThemeScript } from "@/components/brand/theme-script";
import { siteUrl } from "@/lib/site";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: { default: "Open Books by Lumeo", template: "%s | Open Books" },
  description:
    "Open Books turns bank statements, settlements and tax documents into JSON only when its arithmetic proves it, or a typed refusal that says why.",
  applicationName: "Open Books",
  keywords: [
    "bank statement parser",
    "CAMT.053 parser",
    "financial document extraction",
    "bank statement to JSON",
    "OCR bank statements",
    "reconciliation",
    "MCP server",
    "Model Context Protocol",
    "@lumeo_hq/openbooks",
    "openbooks-mcp",
    "Lumeo",
  ],
  authors: [{ name: "Lumeo", url: "https://openbooks.lumeo.co.in" }],
  creator: "Lumeo",
  publisher: "Lumeo",
  category: "technology",
  formatDetection: { email: false, address: false, telephone: false },
  openGraph: {
    type: "website",
    siteName: "Open Books by Lumeo",
    locale: "en_IN",
    images: [{ url: "/og.png", width: 1920, height: 1080, alt: "Open Books by Lumeo: financial documents to proven JSON" }],
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0b0f08" },
    { media: "(prefers-color-scheme: light)", color: "#f7f9f6" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN" className={`${GeistSans.variable} ${GeistMono.variable} ${inter.variable}`} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>{children}</body>
    </html>
  );
}
