import type { Metadata } from "next";
import { QueryProvider } from "../components/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "AXIS Content OS",
  description: "Internal social content operations platform for AXIS Consulting",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><QueryProvider>{children}</QueryProvider></body>
    </html>
  );
}
