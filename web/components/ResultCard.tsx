import Link from 'next/link';
import { CategoryList } from '@/components/CategoryBadge';
import { COPY, SECTION_LABELS } from '@/lib/copy';
import { formatMonth } from '@/lib/format';

export interface ResultCardData {
  id: string;
  drug: string;
  batch: string;
  manufacturer: string;
  /** null when the manufacturer text is a placeholder — there is no page to link. */
  manufacturerSlug: string | null;
  month: string;
  categories: string[];
  section: string;
  disputed: boolean;
}

/**
 * One search result.
 *
 * The whole card is a link to the record page, where the mandatory §1.2 safety
 * copy lives in full. The card itself carries a short standing reminder rather
 * than the full notice — a results list of 100 cards each repeating a five-line
 * warning would train people to scroll past the thing that matters most.
 */
export function ResultCard({ r }: { r: ResultCardData }) {
  const month = formatMonth(r.month);
  return (
    <li className="group relative rounded-lg border border-border bg-card transition-colors duration-200 hover:border-secondary focus-within:border-secondary">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-base font-semibold leading-snug text-foreground break-anywhere">
            <Link
              href={`/record/${r.id}/`}
              className="cursor-pointer after:absolute after:inset-0 after:content-['']"
            >
              {r.drug || COPY.unknownField}
            </Link>
          </h3>
          {r.disputed ? (
            <span className="shrink-0 rounded border border-notice-border bg-notice-soft px-1.5 py-0.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-notice">
              Disputed
            </span>
          ) : null}
        </div>

        <dl className="mt-2.5 grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="text-muted-foreground">Batch</dt>
          <dd className="font-mono text-[0.8125rem] text-foreground break-anywhere">
            {r.batch || COPY.unknownField}
          </dd>

          <dt className="text-muted-foreground">Made by</dt>
          <dd className="text-foreground break-anywhere">{r.manufacturer || COPY.unknownField}</dd>

          <dt className="text-muted-foreground">Flagged</dt>
          <dd className="text-foreground">
            {month ?? COPY.unknownField}
            {r.section ? (
              <span className="text-muted-foreground"> · {SECTION_LABELS[r.section] ?? r.section}</span>
            ) : null}
          </dd>
        </dl>

        {r.categories.length > 0 ? (
          <div className="mt-3">
            <CategoryList categories={r.categories} />
          </div>
        ) : null}
      </div>

      <p className="border-t border-border px-4 py-2 text-xs leading-relaxed text-muted-foreground">
        One tested batch — not a judgement on the whole product. Do not stop a medicine based on
        this; ask your pharmacist or doctor.
      </p>
    </li>
  );
}
