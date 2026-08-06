import Link from 'next/link';
import { COPY } from '@/lib/copy';

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl py-8">
      <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
        Page not found
      </h1>
      <p className="mt-2 text-[0.9375rem] leading-relaxed text-muted-foreground">
        That address does not match a record in MedCheck. If you followed a link to a specific
        batch, it may have been mistyped.
      </p>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">
        {COPY.noResults.detail}
      </p>
      <Link
        href="/"
        className="mt-5 inline-flex min-h-11 cursor-pointer items-center rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors duration-200 hover:border-secondary"
      >
        Go to search
      </Link>
    </div>
  );
}
