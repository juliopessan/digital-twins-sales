import type { Metadata } from "next";
import { IBM_Plex_Mono, Instrument_Serif, Inter_Tight } from "next/font/google";
import "./globals.css";

const display = Inter_Tight({
  variable: "--display-font",
  subsets: ["latin"],
  weight: ["400", "500", "700", "800"],
});

const voice = Instrument_Serif({
  variable: "--voice-font",
  subsets: ["latin"],
  weight: ["400"],
  style: ["italic", "normal"],
});

const mono = IBM_Plex_Mono({
  variable: "--mono-font",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Sales Digital Twins — Board Simulator",
  description:
    "Ensaie o pior comitê de compra da sua vida antes que ele seja real.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body className={`${display.variable} ${voice.variable} ${mono.variable}`}>
        {children}
      </body>
    </html>
  );
}
