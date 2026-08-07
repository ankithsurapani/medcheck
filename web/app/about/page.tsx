import type { Metadata } from 'next';
import Link from 'next/link';
import { SamplingCaveat } from '@/components/Notices';
import { stats } from '@/lib/data';
import { formatMonth } from '@/lib/format';

export const metadata: Metadata = {
  title: 'About the data and its limits',
  description:
    'Where MedCheck’s data comes from, how complete it is, and the limitations you should know before drawing conclusions from it.',
};

export default function AboutPage() {
  const s = stats();
  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="cursor-pointer text-accent underline underline-offset-2">
          Search
        </Link>
        <span className="text-muted-foreground"> / About</span>
      </nav>

      <header>
        <h1 className="font-display text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
          About the data and its limits
        </h1>
        <p className="mt-2 max-w-2xl text-[0.9375rem] leading-relaxed text-muted-foreground">
          MedCheck makes a public dataset searchable. It adds no findings, no ratings and no
          opinions of its own. This page is the part you should read before drawing any conclusion
          from it.
        </p>
      </header>

      <Section title="Where this comes from">
        <p>
          India’s drug regulator, the Central Drugs Standard Control Organisation (CDSCO), buys
          medicine samples from real pharmacies, tests them, and publishes the ones that fail as
          “Not of Standard Quality” (NSQ) or spurious. That data is public, but it is published as
          monthly alerts that cannot be searched.
        </p>
        <p>
          MedCheck holds {s.recordCount.toLocaleString('en-IN')} of those records, covering{' '}
          {s.monthCount} monthly alerts from {formatMonth(s.earliestMonth)} to{' '}
          {formatMonth(s.latestMonth)}. Every record links back to the CDSCO source it came from, so
          nothing here has to be taken on trust.
        </p>
      </Section>

      <Section title="What a flag does and does not mean">
        <p>
          <strong className="font-semibold text-foreground">
            It is not a reason to stop taking a medicine.
          </strong>{' '}
          Stopping treatment for a heart condition, diabetes, epilepsy or a mental health condition
          because of a website is a real risk of harm. If something here concerns you, show it to
          your pharmacist or doctor and ask them.
        </p>
        <p>
          <strong className="font-semibold text-foreground">It applies to one batch.</strong> CDSCO
          tests a specific batch. A flag does not mean other batches of the same medicine failed,
          and it is not a verdict on the manufacturer overall.
        </p>
        <p>
          <strong className="font-semibold text-foreground">
            Not finding something here means very little.
          </strong>{' '}
          Most medicines sold in India are never tested by CDSCO. A medicine that was never tested
          cannot appear in this data. Absence from MedCheck is not a safety check.
        </p>
      </Section>

      <Section title="Known limitations">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong className="font-semibold text-foreground">Sampling is not random.</strong>{' '}
            {`CDSCO chooses what to test. Any count here describes the samples the regulator selected — it is not a failure rate for medicines on the market.`}
          </li>
          <li>
            <strong className="font-semibold text-foreground">
              Manufacturer names are only partly merged.
            </strong>{' '}
            CDSCO re-types the manufacturer name and address every month, so one company appears
            under many spellings. We have grouped them into companies, and every manufacturer page
            lists the exact spellings that went into it so you can check. Pairs we were not
            confident about were reviewed by a person, and where that review has not happened yet
            the spellings were left apart rather than combined — so a company may still have more
            than one page. That is the deliberate direction to be wrong in: wrongly combining two
            companies would attribute one firm’s failures to another.
          </li>
          <li>
            <strong className="font-semibold text-foreground">
              Manufacturing state is sometimes missing, and sometimes inferred.
            </strong>{' '}
            CDSCO publishes the manufacturer as one block of text with the address inside it, and
            usually does not name the state — the address just ends in a PIN code. Where it does
            name one, we use it. Where it does not, we use the state that PIN code belongs to and
            say so on the record. Where neither works — no PIN, or a PIN whose range covers more
            than one state — we show nothing rather than guess.
          </li>
          <li>
            <strong className="font-semibold text-foreground">
              Some stated reasons do not map to a known test.
            </strong>{' '}
            Where CDSCO’s wording does not match a standard test category we label it “Other” and
            show the regulator’s original text rather than forcing it into a category.
          </li>
          <li>
            <strong className="font-semibold text-foreground">Coverage starts in 2019.</strong>{' '}
            CDSCO’s searchable data portal begins then. Older alerts exist only as PDFs and are not
            loaded yet.
          </li>
          <li>
            <strong className="font-semibold text-foreground">
              The regulator’s own sources sometimes disagree.
            </strong>{' '}
            For at least one month, CDSCO’s data portal and its published PDF differ on which
            records exist and on whether a central or state laboratory did the testing. Where they
            differ, we show what the portal published and link to it.
          </li>
        </ul>
        <SamplingCaveat className="mt-1" />
      </Section>

      <Section title="Your privacy">
        <p>
          MedCheck stores nothing about who searched for what. There are no accounts, no login and
          no tracking tied to a person. Searching happens entirely inside your own browser — the
          data is downloaded once and queried on your device, so your searches are not sent
          anywhere at all.
        </p>
      </Section>

      <Section title="Corrections">
        <p>
          If a record here does not match what CDSCO published, the CDSCO source is correct and we
          are wrong. Every record page links to that source so the difference can be checked
          directly.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-lg font-bold text-foreground">{title}</h2>
      <div className="mt-2 max-w-2xl space-y-3 text-[0.9375rem] leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}
