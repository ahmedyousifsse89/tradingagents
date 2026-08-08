import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "TradingAgents Control",
  description: "Control dashboard for the TradingAgents execution bot.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
