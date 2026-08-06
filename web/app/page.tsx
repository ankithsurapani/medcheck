import Link from 'next/link';
import { Search } from '@/components/Search';
import { SafetyNotice, SamplingCaveat } from '@/components/Notices';
import { stats } from '@/lib/data';
import { formatMonth } from '@/lib/format';

export default function HomePage() {
  const s = stats();
  return (
    <div className="space-y-8">
      {/* The safety notice sits above the fold on the landing page too, not only
          on results — someone arriving worried should read it before searching. */}
      <SafetyNotice />

      <Search recordCount={s.recordCount} />

      <section aria-labelledby="coverage-heading" className="border-t border-border pt-6">
        <h2 id="coverage-heading" className="font-display text-lg font-bold text-foreground">
          What is in here
        </h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Flagged batches" value={s.recordCount.toLocaleString('en-IN')} />
          <Stat label="Monthly alerts" value={String(s.monthCount)} />
          <Stat
            label="Manufacturers"
            value={s.manufacturerCount.toLocaleString('en-IN')}
            note={`from ${s.rawSpellingCount.toLocaleString('en-IN')} published spellings`}
          />
          <Stat label="Marked disputed" value={String(s.disputedCount)} />
        </dl>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Covering CDSCO alerts from {formatMonth(s.earliestMonth)} to {formatMonth(s.latestMonth)}.
          Every record links to the regulator’s own published source.
        </p>
        <SamplingCaveat className="mt-2" />
        <p className="mt-3 text-sm">
          <Link href="/about/" className="cursor-pointer text-accent underline underline-offset-2">
            Read the limitations before drawing conclusions
          </Link>
        </p>
      </section>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-display text-xl font-bold tabular-nums text-foreground">{value}</dd>
      {note ? <p className="mt-0.5 text-[0.6875rem] text-muted-foreground">{note}</p> : null}
    </div>
  );
}
