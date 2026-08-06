import type { Metadata } from 'next';
import Link from 'next/link';
import { ALL_CATEGORIES, FAILURE_CATEGORIES } from '@/lib/failure-categories';
import { SamplingCaveat } from '@/components/Notices';

export const metadata: Metadata = {
  title: 'What the test types mean',
  description:
    'Plain-language explanations of every test category CDSCO records against a flagged batch — assay, dissolution, sterility, endotoxins and the rest.',
};

export default function CategoriesPage() {
  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="cursor-pointer text-accent underline underline-offset-2">
          Search
        </Link>
        <span className="text-muted-foreground"> / Test types</span>
      </nav>

      <header>
        <h1 className="font-display text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl">
          What the test types mean
        </h1>
        <p className="mt-2 max-w-2xl text-[0.9375rem] leading-relaxed text-muted-foreground">
          When CDSCO flags a batch it records which laboratory test the sample failed. These are
          explanations of what each test measures. They describe the finding only — what it means
          for you specifically is a question for your pharmacist or doctor.
        </p>
        <SamplingCaveat className="mt-3" />
      </header>

      <ul className="grid gap-3 sm:grid-cols-2">
        {ALL_CATEGORIES.map((key) => {
          const info = FAILURE_CATEGORIES[key];
          return (
            <li key={key} id={key} className="rounded-lg border border-border bg-card p-4">
              <h2 className="font-display text-base font-semibold text-foreground">{info.label}</h2>
              <p className="mt-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                {info.short}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {info.explanation}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
