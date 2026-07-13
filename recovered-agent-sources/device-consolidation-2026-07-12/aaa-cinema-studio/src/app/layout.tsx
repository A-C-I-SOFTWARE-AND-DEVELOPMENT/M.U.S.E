import type { Metadata } from "next";
import { Geist, Geist_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const display = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "muse — Multi-Use Synaptic Entity",
  description:
    "muse: one mind, many pathways. The state-of-the-art AI harness for AAA game worlds and cinematic theatrical films — from logline to gold master.",
  keywords: ["muse", "MUSE", "AAA games", "cinematic films", "AI studio", "narrative engine", "worldbuilding", "storyboard"],
  authors: [{ name: "muse" }],
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "muse — Multi-Use Synaptic Entity",
    description: "One mind, many pathways. AAA games & cinematic films, end to end.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${display.variable} antialiased bg-background text-foreground relative`}
      >
        <ThemeProvider attribute="class" forcedTheme="dark" enableSystem={false}>
          <div className="relative z-10 min-h-screen flex flex-col">
            {children}
          </div>
          <SonnerToaster
            position="bottom-right"
            theme="dark"
            toastOptions={{
              style: {
                background: 'var(--void-3)',
                border: '1px solid var(--edge)',
                color: '#e8ecf4',
              },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
