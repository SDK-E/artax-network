import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Artax Network Dashboard",
  description: "Real-time dashboard for the Artax event-driven runtime",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-artax-navy">
        {children}
      </body>
    </html>
  );
}
