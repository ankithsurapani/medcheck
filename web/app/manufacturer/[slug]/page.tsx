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
  const name = m.name.split(',')[0];
  return {
    title: `${name} — flagged batches`,
    description: `CDSCO records published under the manufacturer text “${name}”. ${m.count} flagged ${
      m.count === 1 ? 'batch' : 'batches'
    }.`,
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
  const isPlaceholder = /^\s*(under investigation|not known|unknown)\s*$/i.test(m.name);

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="cursor-pointer text-accent underline underline-offset-2">
          Search
        </Link>
        <span className="text-muted-foreground"> / Manufacturer</span>
      </nav>

      <header>
        <p className="text-sm text-muted-foreground">Manufacturer, as published by CDSCO</p>
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
        </p>
      </header>

      {/* Phase 2 (entity resolution) has not run. Saying so plainly is required:
          presenting this as "the company's record" would overstate it, and
          silently merging near-identical names would risk attributing one
          company's failures to another (plan.md §5.3). */}
      {isPlaceholder ? (
        <aside role="note" className="rounded-lg border-2 border-notice-border bg-notice-soft p-4">
          <h2 className="font-display text-[0.9375rem] font-bold text-notice">
            This is not a company
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground">
            CDSCO published “{m.name}” in the manufacturer field for these batches, because the real
            manufacturer is not known. These are grouped only so the records are reachable — they
            are not the work of one company.
          </p>
        </aside>
      ) : (
        <aside role="note" className="rounded-lg border border-accent-border bg-accent-soft p-4">
          <h2 className="font-display text-[0.9375rem] font-semibold text-foreground">
            {COPY.manufacturerPage.rawNameNotice}
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            {COPY.manufacturerPage.rawNameBody}
          </p>
        </aside>
      )}

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
                disputed: r.labelClaimDisputed === 1,
              }}
            />
          ))}
        </ul>
      </section>
    </div>
  );
}
