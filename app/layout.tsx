import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/styles/globals.css";
import { PRODUCT_NAME } from "@/lib/brand";
import { DirectionProvider } from "@/components/foundations/direction/direction";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], axes: ["opsz"] });

export const metadata: Metadata = {
  title: PRODUCT_NAME,
  description: `${PRODUCT_NAME} mission view`,
};

// runs before paint: saved choice wins, otherwise follow the system setting
const themeScript = `(function(){var k="boardui:theme",m=window.matchMedia("(prefers-color-scheme: dark)");function saved(){try{var v=localStorage.getItem(k);return v==="dark"||v==="light"?v:null}catch(e){return null}}function set(){document.documentElement.classList.toggle("dark",(saved()||(m.matches?"dark":"light"))==="dark")}set();m.addEventListener("change",function(){if(!saved()){set();window.dispatchEvent(new CustomEvent("boardui:theme-change"))}})})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full bg-background-full text-text-primary">
        <DirectionProvider locale="en-US">{children}</DirectionProvider>
      </body>
    </html>
  );
}
