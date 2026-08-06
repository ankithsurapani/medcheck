import { COPY } from '@/lib/copy';

/**
 * The non-negotiable notices from plan.md §1. These are constraints, not
 * decoration — SafetyNotice must appear on every result surface and must not be
 * dismissible, so there is deliberately no close button and no collapsed state.
 */

function IconInfo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 11v5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="7.75" r="1" fill="currentColor" />
    </svg>
  );
}

function IconFlag({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <path
        d="M5 21V4.5M5 4.5h11l-1.8 3.2L16 11H5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconLayers({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <path
        d="M12 3.5 3.5 8l8.5 4.5L20.5 8 12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M4 12.5 12 17l8-4.5M4 16.5 12 21l8-4.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * plan.md §1.2 — required on every result page, non-dismissible.
 * Given the most visual weight on the page on purpose: of everything here, this
 * is the message whose absence could cause actual harm.
 */
export function SafetyNotice() {
  return (
    <aside
      role="note"
      aria-labelledby="safety-heading"
      className="rounded-lg border-2 border-safety-border bg-safety-soft p-4 sm:p-5"
    >
      <div className="flex gap-3">
        <IconInfo className="mt-0.5 h-6 w-6 shrink-0 text-safety" />
        <div>
          <h2 id="safety-heading" className="font-display text-base font-bold text-safety sm:text-lg">
            {COPY.safety.heading}
          </h2>
          <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-foreground">
            {COPY.safety.body}
          </p>
        </div>
      </div>
    </aside>
  );
}

/** plan.md §1.3 — visible on every result, never footnoted. */
export function BatchNotProductNotice() {
  return (
    <aside
      role="note"
      aria-labelledby="batch-heading"
      className="rounded-lg border border-border bg-card p-4"
    >
      <div className="flex gap-3">
        <IconLayers className="mt-0.5 h-5 w-5 shrink-0 text-secondary" />
        <div>
          <h2 id="batch-heading" className="font-display text-[0.9375rem] font-semibold text-foreground">
            {COPY.batchNotProduct.heading}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {COPY.batchNotProduct.body}
          </p>
        </div>
      </div>
    </aside>
  );
}

/** plan.md §5.5 — only when label_claim_disputed is true. Prominent, never buried. */
export function DisputedNotice({ firmWording }: { firmWording?: string | null }) {
  return (
    <aside
      role="note"
      aria-labelledby="disputed-heading"
      className="rounded-lg border-2 border-notice-border bg-notice-soft p-4 sm:p-5"
    >
      <div className="flex gap-3">
        <IconFlag className="mt-0.5 h-5 w-5 shrink-0 text-notice" />
        <div>
          <h2 id="disputed-heading" className="font-display text-base font-bold text-notice">
            {COPY.disputed.heading}
          </h2>
          <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-foreground">
            {COPY.disputed.body}
          </p>
          {firmWording ? (
            <blockquote className="mt-3 border-l-2 border-notice-border pl-3 text-sm italic leading-relaxed text-muted-foreground break-anywhere">
              {firmWording}
            </blockquote>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

/** plan.md §1.4 — uncertainty is displayed, not hidden. */
export function UncertaintyNotice({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <aside
      role="note"
      aria-labelledby="uncertainty-heading"
      className="rounded-lg border border-accent-border bg-accent-soft p-4"
    >
      <h2 id="uncertainty-heading" className="font-display text-[0.9375rem] font-semibold text-foreground">
        {COPY.lowConfidence.heading}
      </h2>
      <ul className="mt-2 space-y-1.5">
        {notes.map((n) => (
          <li key={n} className="flex gap-2 text-sm leading-relaxed text-muted-foreground">
            <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
            <span>{n}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/** Shown wherever a count or rate appears (plan.md §1, sampling bias). */
export function SamplingCaveat({ className = '' }: { className?: string }) {
  return (
    <p className={`text-xs leading-relaxed text-muted-foreground ${className}`}>
      {COPY.samplingCaveat}
    </p>
  );
}
