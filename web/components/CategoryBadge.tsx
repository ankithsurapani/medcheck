import { categoryInfo } from '@/lib/failure-categories';

/**
 * A failure category chip. Amber, never red: plan.md §1.1 — MedCheck reports
 * what the regulator found, it does not raise an alarm about it.
 *
 * Category is conveyed by text, not colour alone, so it survives greyscale and
 * colour-blindness (the "don't rely on colour" rule in the UX guidelines).
 */
export function CategoryBadge({ category }: { category: string }) {
  const info = categoryInfo(category);
  const isSpurious = category === 'spurious';
  return (
    <span
      title={info.short}
      className={[
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        isSpurious
          ? 'border-notice-border bg-notice-soft text-notice'
          : 'border-accent-border bg-accent-soft text-accent',
      ].join(' ')}
    >
      {info.label}
    </span>
  );
}

export function CategoryList({ categories }: { categories: string[] }) {
  if (categories.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {categories.map((c) => (
        <li key={c}>
          <CategoryBadge category={c} />
        </li>
      ))}
    </ul>
  );
}
