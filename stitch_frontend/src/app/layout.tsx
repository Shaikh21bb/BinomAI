import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Manrope } from "next/font/google";
import { Providers } from "@/components/Providers";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin", "cyrillic"],
});

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: "BINOM AI — рабочее пространство",
  description: "AI-first Procurement",
  metadataBase: new URL("https://binom.ai"),
  openGraph: {
    title: "BINOM AI — AI-ассистент для участников закупок",
    description:
      "Анализ тендерной документации, уточняющие вопросы и автоматическая подготовка коммерческих предложений, технических заданий и сопроводительных писем на русском и казахском языках.",
    type: "website",
    locale: "ru_RU",
  },
  twitter: {
    card: "summary_large_image",
    title: "BINOM AI — AI-ассистент для участников закупок",
    description:
      "Анализ тендерной документации, уточняющие вопросы и автоматическая подготовка коммерческих предложений, технических заданий и сопроводительных писем на русском и казахском языках.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{document.documentElement.classList.add('js');var t=localStorage.getItem('binom-theme');if(t!=='dark'&&t!=='light'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.dataset.theme=t}catch(e){}})();`,
          }}
        />
      </head>
      <body
        className={`theme-tenderpro ${inter.variable} ${jetbrainsMono.variable} ${manrope.variable} antialiased bg-surface text-on-surface font-body-md flex w-full min-h-screen overflow-x-hidden`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
