import type { Metadata } from "next";
import "./globals.css";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "AutoSlice — 3MF Converter",
  description: "Convert Bambu/MakerWorld 3MF files to optimized Anycubic print profiles.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Footer />
      </body>
    </html>
  );
}
