import type { Metadata } from "next";
import "./globals.css";
import { LangProvider } from "@/contexts/LangContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { UnitsProvider } from "@/contexts/UnitsContext";

export const metadata: Metadata = {
  title: "AutoSlice — One File. Any Slice.",
  description: "Upload, analyze, optimize and translate supported 3MF projects for the slicer and printer you choose.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <UnitsProvider>
            <LangProvider>
              {children}
            </LangProvider>
          </UnitsProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
