import type { Metadata } from 'next';
import { Figtree, Noto_Sans } from 'next/font/google';
import Link from 'next/link';
import './globals.css';
import { COPY } from '@/lib/copy';

/**
 * Figtree for display, Noto Sans for body — the pairing the design system
 * recommends for healthcare (clean, accessible, trustworthy). Noto Sans also
 * carries full Devanagari coverage, which is what Phase 3b's Hindi translation
 * will need, so the type choice doesn't have to be revisited then.
 */
const figtree = Figtree({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-figtree',
  display: 'swap',
});

const notoSans = Noto_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-noto-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'MedCheck — search medicines flagged by India’s drug regulator',
    template: '%s · MedCheck',
  },
  description:
    'Search CDSCO’s published Not of Standard Quality (NSQ) and spurious drug alerts by medicine name, batch number or manufacturer. A searchable mirror of public regulator data.',
  robots: { index: true, follow: true },
};

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  // Deliberately not disabling zoom — pinch-zoom is an accessibility necessity
  // and this page carries information people may need to enlarge.
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${figtree.variable} ${notoSans.variable}`}>
      <body className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow"
        >
          Skip to content
        </a>

        <header className="border-b border-border bg-card">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
            <Link
              href="/"
              className="group flex cursor-pointer items-center gap-2"
              aria-label={`${COPY.siteName} home`}
            >
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-6 w-6 text-accent">
                <path
                  d="M12 3.2 5 6v5.4c0 4.2 2.9 7.6 7 9.4 4.1-1.8 7-5.2 7-9.4V6l-7-2.8Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="m9.2 12.1 2 2 3.6-3.9"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className="font-display text-lg font-bold tracking-tight text-foreground">
                {COPY.siteName}
              </span>
            </Link>
            <nav aria-label="Main">
              <ul className="flex items-center gap-1">
                <li>
                  <Link
                    href="/categories/"
                    className="inline-flex min-h-11 cursor-pointer items-center rounded px-2.5 text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:px-3"
                  >
                    Test types
                  </Link>
                </li>
                <li>
                  <Link
                    href="/about/"
                    className="inline-flex min-h-11 cursor-pointer items-center rounded px-2.5 text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:px-3"
                  >
                    About
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:py-8">
          {children}
        </main>

        <footer className="mt-8 border-t border-border bg-card">
          <div className="mx-auto max-w-5xl px-4 py-6">
            <p className="text-sm text-muted-foreground">
              MedCheck mirrors data published by the Central Drugs Standard Control Organisation
              (CDSCO). It is not affiliated with CDSCO or any government body, and it adds no
              judgement of its own — every record links to the regulator’s own source.
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              MedCheck stores nothing about who searched for what. There are no accounts and no
              per-person tracking.
            </p>
            <p className="mt-3 text-sm">
              <Link href="/about/" className="cursor-pointer text-accent underline underline-offset-2">
                How this data was collected and its limitations
              </Link>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
