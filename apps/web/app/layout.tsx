import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "QuantPilot | Research workspace",
  description: "Explainable quantitative research. Personal decision support.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
