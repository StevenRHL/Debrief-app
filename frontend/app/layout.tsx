import type { Metadata } from "next";
import "./globals.css";
import Nav from "./nav";
import MockBadge from "./mock-badge";

export const metadata: Metadata = {
  title: "Debrief",
  description: "Explain your reasoning. Get graded on how you think, not whether you guessed right.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Fixed badge lives in the layout so every page — landing, play,
            progress, login — visibly shows fixture/live mode in any recording.
            MockBadge fetches per-domain status and spells out any live domains. */}
        <MockBadge />
        <Nav />
        {children}
      </body>
    </html>
  );
}
