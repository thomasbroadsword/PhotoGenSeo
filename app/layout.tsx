import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PhotoGenSeo – opisy produktów",
  description: "Wsadowe generowanie opisów SEO ze zdjęć (EAN, walidacja, eksport CSV).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pl">
      <body>{children}</body>
    </html>
  );
}
