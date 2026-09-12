import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "GitChat – AI Code Assistant",
  description:
    "Ask questions about any GitHub repository using AI-powered RAG: semantic search, AST-based chunking, and GPT-4o streaming.",
  keywords: ["GitHub", "AI", "code assistant", "RAG", "GPT-4o", "semantic search"],
  authors: [{ name: "GitChat" }],
  openGraph: {
    title: "GitChat – AI Code Assistant",
    description: "Chat with any GitHub repository using AI and RAG",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "GitChat – AI Code Assistant",
    description: "Chat with any GitHub repository using AI and RAG",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full`}
    >
      <body className="h-full overflow-hidden">{children}</body>
    </html>
  );
}
