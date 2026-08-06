import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { CategoryList } from '@/components/CategoryBadge';
import {
  BatchNotProductNotice,
  DisputedNotice,
  SafetyNotice,
  UncertaintyNotice,
} from '@/components/Notices';
import { COPY, SECTION_DESCRIPTIONS, SECTION_LABELS } from '@/lib/copy';
import { allRecords, getRecord, type MedRecord } from '@/lib/data';
import { categoryInfo } from '@/lib/failure-categories';
import { formatMonth, userFacingFlags } from '@/lib/format';

export const dynamicParams = false;

export function generateStaticParams() {
  return allRecords().map((r) => ({ id: r.id }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ id: string }> },
): Promise<Metadata> {
  const { id } = await params;
  const r = getRecord(id);
  if (!r) return { title: 'Record not found' };
  const month = formatMonth(r.alertMonth);
  return {
    title: `${r.drugName ?? 'Record'} — batch ${r.batchNumber ?? 'unknown'}`,
    description: `CDSCO flagged batch ${r.batchNumber ?? ''} of ${r.drugName ?? 'this product'}${
      month ? ` in ${month}` : ''
    }. Published test result, manufacturer and source link.`,
  };
}

/** A field that is absent is stated as absent, never left blank (plan.md §1.4). */
function Field({
  label,
  value,
  mono = false,
  hint,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  hint?: string;
}) {
  const missing = value === null || value === undefined || value === '';
  return (
    <div className="border-b border-border py-3 last:border-b-0 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd
        className={[
          'mt-0.5 break-anywhere sm:mt-0',
          mono ? 'font-mono text-[0.9375rem]' : 'text-[0.9375rem]',
          missing ? 'text-muted-foreground italic' : 'text-foreground',
        ].join(' ')}
      >
        {missing ? COPY.unknownField : value}
        {missing && hint ? (
          <span className="mt-0.5 block text-xs not-italic text-muted-foreground">{hint}</span>
        ) : null}
      </dd>
    </div>
  );
}

export default async function RecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = getRecord(id);
  if (!r) notFound();
  return <RecordView r={r} />;
}

function RecordView({ r }: { r: MedRecord }) {
  const month = formatMonth(r.alertMonth);
  const disputed = r.labelClaimDisputed === 1;
  const flagNotes = userFacingFlags(r.parseFlags);

  // The firm's own wording is appended to failure_reason_raw by the normalizer,
  // marked "[Firm's reply]". Split it back out so the dispute notice can quote
  // the company verbatim rather than paraphrasing it (plan.md §1.1).
  const reason = r.failureReason ?? '';
  const firmIdx = reason.indexOf("[Firm's reply]");
  const testResult = firmIdx >= 0 ? reason.slice(0, firmIdx).trim() : reason;
  const firmWording = firmIdx >= 0 ? reason.slice(firmIdx).trim() : null;

  return (
    <article className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="cursor-pointer text-accent underline underline-offset-2">
          Search
        </Link>
        <span className="text-muted-foreground"> / Flagged batch</span>
      </nav>

      <header>
        <h1 className="font-display text-2xl font-bold leading-tight tracking-tight text-foreground break-anywhere sm:text-3xl">
          {r.drugName ?? COPY.unknownField}
        </h1>
        <p className="mt-1.5 text-[0.9375rem] text-muted-foreground">
          Batch <span className="font-mono text-foreground">{r.batchNumber ?? '—'}</span>
          {month ? <> · flagged {month}</> : null}
        </p>
        {r.failureCategories.length > 0 ? (
          <div className="mt-3">
            <CategoryList categories={r.failureCategories} />
          </div>
        ) : null}
      </header>

      {/* Order is deliberate. §1.2 first — it is the one message that prevents
          harm. Then §5.5 if the batch is disputed, then §1.3. */}
      <SafetyNotice />
      {disputed ? <DisputedNotice firmWording={firmWording} /> : null}
      <BatchNotProductNotice />

      <section aria-labelledby="finding-heading">
        <h2 id="finding-heading" className="font-display text-lg font-bold text-foreground">
          What the lab found
        </h2>

        {r.failureCategories.length > 0 ? (
          <ul className="mt-3 space-y-3">
            {r.failureCategories.map((c) => {
              const info = categoryInfo(c);
              return (
                <li key={c} className="rounded-lg border border-border bg-card p-4">
                  <h3 className="font-display text-[0.9375rem] font-semibold text-foreground">
                    {info.label}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {info.explanation}
                  </p>
                </li>
              );
            })}
          </ul>
        ) : null}

        <div className="mt-4 rounded-lg border border-border bg-muted p-4">
          <h3 className="text-sm font-semibold text-foreground">CDSCO’s exact wording</h3>
          <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-foreground break-anywhere">
            {testResult || COPY.unknownField}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Reproduced unchanged. Where our plain-language summary and this differ, this is what the
            regulator published.
          </p>
        </div>
      </section>

      <UncertaintyNotice notes={flagNotes} />

      <section aria-labelledby="details-heading">
        <h2 id="details-heading" className="font-display text-lg font-bold text-foreground">
          Record details
        </h2>
        <dl className="mt-2 rounded-lg border border-border bg-card px-4">
          <Field label="Medicine" value={r.drugName} />
          <Field label="Batch number" value={r.batchNumber} mono />
          <Field label="Dosage form" value={r.dosageForm} hint={COPY.unknownFieldHint} />
          <Field label="Manufactured" value={formatMonth(r.mfgDate)} hint={COPY.unknownFieldHint} />
          <Field label="Expires" value={formatMonth(r.expiryDate)} hint={COPY.unknownFieldHint} />
          <Field label="Alert month" value={month} />
          <Field label="Tested by" value={r.testingLab} hint={COPY.unknownFieldHint} />
          <Field
            label="Manufacturing state"
            value={r.state}
            hint="CDSCO published an address this could not be read from unambiguously"
          />
          <div className="border-b border-border py-3 last:border-b-0 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-4">
            <dt className="text-sm text-muted-foreground">Reporting source</dt>
            <dd className="mt-0.5 text-[0.9375rem] text-foreground sm:mt-0">
              {r.alertSection ? SECTION_LABELS[r.alertSection] ?? r.alertSection : COPY.unknownField}
              {r.alertSection && SECTION_DESCRIPTIONS[r.alertSection] ? (
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  {SECTION_DESCRIPTIONS[r.alertSection]}
                </span>
              ) : null}
            </dd>
          </div>
          <div className="py-3 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-4">
            <dt className="text-sm text-muted-foreground">Manufacturer</dt>
            <dd className="mt-0.5 text-[0.9375rem] sm:mt-0">
              <Link
                href={`/manufacturer/${r.manufacturerSlug}/`}
                className="cursor-pointer text-accent underline underline-offset-2 break-anywhere"
              >
                {r.manufacturer || COPY.unknownField}
              </Link>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                As printed on the packaging and published by CDSCO.
                {disputed ? ' The company named says this batch is not theirs — see above.' : ''}
              </span>
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="source-heading">
        <h2 id="source-heading" className="font-display text-lg font-bold text-foreground">
          Check it yourself
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          MedCheck adds nothing to this record. This link goes to the CDSCO data it came from.
        </p>
        <a
          href={r.sourceUrl}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="mt-3 inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors duration-200 hover:border-secondary"
        >
          Open the CDSCO source
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-4 w-4">
            <path
              d="M14 4h6v6M20 4l-8.5 8.5M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="sr-only">(opens in a new tab)</span>
        </a>
        <p className="mt-2 text-xs text-muted-foreground break-anywhere">
          Source type: {r.sourceType === 'portal_json' ? 'CDSCO public data portal' : 'CDSCO alert PDF'}
          {' · '}Record id: <span className="font-mono">{r.id}</span>
        </p>
      </section>
    </article>
  );
}
