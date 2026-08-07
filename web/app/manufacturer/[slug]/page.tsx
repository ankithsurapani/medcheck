import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ResultCard } from '@/components/ResultCard';
import { SafetyNotice, SamplingCaveat } from '@/components/Notices';
import { COPY } from '@/lib/copy';
import { allManufacturers, getManufacturer, recordsFor } from '@/lib/data';
import { formatMonth } from '@/lib/format';

export const dynamicParams = false;

export function generateStaticParams() {
  return allManufacturers().map((m) => ({ slug: m.slug }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  const m = getManufacturer(slug);
  if (!m) return { title: 'Manufacturer not found' };
  return {
    title: `${m.name} — flagged batches`,
    description: `CDSCO records for ${m.name}, combined across ${m.aliases.length} published ${
      m.aliases.length === 1 ? 'spelling' : 'spellings'
    }. ${m.count} flagged ${m.count === 1 ? 'batch' : 'batches'}.`,
  };
}

export default async function ManufacturerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const m = getManufacturer(slug);
  if (!m) notFound();

  const records = recordsFor(m);
  const months = records.map((r) => r.alertMonth).filter(Boolean) as string[];
  const earliest = months.length ? months[months.length - 1] : null;
  const latest = months.length ? months[0] : null;
  const aliasCount = m.aliases.length;

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="cursor-pointer text-accent underline underline-offset-2">
          Search
        </Link>
        <span className="text-muted-foreground"> / Manufacturer</span>
      </nav>

      <header>
        <p className="text-sm text-muted-foreground">Manufacturer</p>
        <h1 className="mt-1 font-display text-xl font-bold leading-snug tracking-tight text-foreground break-anywhere sm:text-2xl">
          {m.name}
        </h1>
        <p className="mt-2 text-[0.9375rem] text-muted-foreground">
          {m.count} flagged {m.count === 1 ? 'batch' : 'batches'}
          {earliest && latest
            ? earliest === latest
              ? ` · ${formatMonth(latest)}`
              : ` · ${formatMonth(earliest)} to ${formatMonth(latest)}`
            : null}
          {m.state ? ` · ${m.state}` : null}
        </p>
        {m.addressRaw ? (
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground break-anywhere">
            <span className="text-foreground">{COPY.manufacturerPage.addressHeading}:</span>{' '}
            {m.addressRaw}
          </p>
        ) : null}
      </header>

      {/* Phase 2a merged spellings onto companies with a human deciding the
          ambiguous band, so the Phase 3a "one spelling only" disclaimer is gone.
          What replaces it is smaller but still honest: the merge is real, it is
          checked, and it is not finished — pairs nobody was confident about were
          left apart, so a company can still have more than one page. Overstating
          the merge would risk exactly the misattribution plan.md §5.3 warns
          about. */}
      <aside role="note" className="rounded-lg border border-accent-border bg-accent-soft p-4">
        {aliasCount > 1 ? (
          <>
            <h2 className="font-display text-[0.9375rem] font-semibold text-foreground">
              {COPY.manufacturerPage.mergedNotice}
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              {COPY.manufacturerPage.mergedBody}
            </p>
          </>
        ) : null}
        <p
          className={[
            'text-sm leading-relaxed text-muted-foreground',
            aliasCount > 1 ? 'mt-2' : '',
          ].join(' ')}
        >
          {COPY.manufacturerPage.partialNotice}
        </p>
      </aside>

      <section aria-labelledby="aliases-heading">
        <h2
          id="aliases-heading"
          className="font-display text-lg font-bold text-foreground"
        >
          {COPY.manufacturerPage.aliasHeading(aliasCount)}
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {COPY.manufacturerPage.aliasBody}
        </p>
        {/* Jackson Laboratories has 67 of these, each up to 328 characters. Open
            by default up to a handful; past that it would push the batch list off
            the screen, so it collapses — but it is never truncated or elided. */}
        <details className="mt-3 rounded-lg border border-border bg-card" open={aliasCount <= 5}>
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground marker:text-muted-foreground">
            {aliasCount === 1 ? 'Show the entry' : `Show all ${aliasCount} spellings`}
          </summary>
          <ul className="border-t border-border px-4 py-3 text-sm">
            {m.aliases.map((a) => (
              <li
                key={a}
                className="border-b border-border py-2 leading-relaxed text-muted-foreground break-anywhere last:border-b-0"
              >
                {a}
              </li>
            ))}
          </ul>
        </details>
      </section>

      <SafetyNotice />

      <section aria-labelledby="records-heading">
        <h2 id="records-heading" className="font-display text-lg font-bold text-foreground">
          Flagged batches
        </h2>
        <SamplingCaveat className="mt-1" />
        <ul className="mt-3 grid gap-3">
          {records.map((r) => (
            <ResultCard
              key={r.id}
              r={{
                id: r.id,
                drug: r.drugName ?? '',
                batch: r.batchNumber ?? '',
                manufacturer: r.manufacturer,
                manufacturerSlug: r.manufacturerSlug,
                month: r.alertMonth ?? '',
                categories: r.failureCategories,
                section: r.alertSection ?? '',
                labType: (r.labType as 'central' | 'state' | 'unknown') ?? 'unknown',
                disputed: r.labelClaimDisputed === 1,
              }}
            />
          ))}
        </ul>
      </section>
    </div>
  );
}
