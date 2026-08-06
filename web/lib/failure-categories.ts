/**
 * Plain-language explanations for every failure_category bucket (plan.md §3.3).
 *
 * Tone rules, from plan.md §1:
 *  - Factual and non-alarming. Describe the lab finding, not its consequences
 *    for a patient. We are not qualified to state those and §1.2 forbids
 *    implying anyone should stop treatment.
 *  - Never editorialise about the manufacturer (§1.1).
 *  - Say what the test measures, so a reader can take the question to a
 *    pharmacist with the right words.
 *
 * All user-facing strings live in this one module rather than inline in
 * components, so Phase 3b can add a Hindi map beside this one without touching
 * any component.
 */

export type FailureCategory =
  | 'assay'
  | 'dissolution'
  | 'disintegration'
  | 'sterility'
  | 'microbial_contamination'
  | 'bacterial_endotoxins'
  | 'particulate_matter'
  | 'related_substances'
  | 'identification'
  | 'description_labelling'
  | 'ph'
  | 'water_content'
  | 'loss_on_drying'
  | 'uniformity_of_weight'
  | 'uniformity_of_dispersion'
  | 'density'
  | 'extractable_volume'
  | 'clarity_of_solution'
  | 'dimensions'
  | 'spurious'
  | 'other';

export interface CategoryInfo {
  label: string;
  short: string;
  explanation: string;
}

export const FAILURE_CATEGORIES: Record<FailureCategory, CategoryInfo> = {
  assay: {
    label: 'Assay',
    short: 'Amount of active ingredient',
    explanation:
      'Lab testing found the amount of active ingredient in this batch fell outside the range the standard allows. That can mean more or less than the label states.',
  },
  dissolution: {
    label: 'Dissolution',
    short: 'How the medicine dissolves',
    explanation:
      'The tablet or capsule did not dissolve at the expected rate in lab testing. Dissolution affects how much of the medicine the body can absorb.',
  },
  disintegration: {
    label: 'Disintegration',
    short: 'How the tablet breaks apart',
    explanation:
      'The tablet or capsule did not break apart within the time the standard allows. Disintegration is the step before the medicine can dissolve.',
  },
  sterility: {
    label: 'Sterility',
    short: 'Freedom from living organisms',
    explanation:
      'This batch did not pass the test confirming it is free of living micro-organisms. Sterility is required for injections and other products that bypass the body’s natural barriers.',
  },
  microbial_contamination: {
    label: 'Microbial contamination',
    short: 'Micro-organisms above the limit',
    explanation:
      'Testing found micro-organisms above the level the standard permits for this type of product.',
  },
  bacterial_endotoxins: {
    label: 'Bacterial endotoxins',
    short: 'Substances left by bacteria',
    explanation:
      'Testing found bacterial endotoxins above the permitted limit. Endotoxins are substances released by bacteria, and they can remain even after the bacteria themselves are gone — which is why this is tested separately from sterility.',
  },
  particulate_matter: {
    label: 'Particulate matter',
    short: 'Visible or sub-visible particles',
    explanation:
      'Testing found particles in the product above the number the standard permits. This is checked closely in injections and other liquids.',
  },
  related_substances: {
    label: 'Related substances',
    short: 'Impurities and breakdown products',
    explanation:
      'Testing found impurities or breakdown products above the permitted limit. These can form as a medicine ages or from the manufacturing process.',
  },
  identification: {
    label: 'Identification',
    short: 'Whether the stated ingredient is present',
    explanation:
      'The test used to confirm the stated active ingredient is present did not give the expected result for this batch.',
  },
  description_labelling: {
    label: 'Description and labelling',
    short: 'Appearance or label details',
    explanation:
      'The batch did not match its described appearance, or the label was missing or misstating information the rules require.',
  },
  ph: {
    label: 'pH',
    short: 'Acidity or alkalinity',
    explanation:
      'The acidity or alkalinity of this batch fell outside the range the standard specifies. pH affects how stable a medicine is and how it is tolerated.',
  },
  water_content: {
    label: 'Water content',
    short: 'Moisture level',
    explanation:
      'The amount of water in this batch fell outside the permitted range. Moisture can affect how stable a medicine stays over its shelf life.',
  },
  loss_on_drying: {
    label: 'Loss on drying',
    short: 'Total volatile content',
    explanation:
      'The amount of material lost when the sample was dried fell outside the permitted range. This measures all substances that evaporate, not water alone.',
  },
  uniformity_of_weight: {
    label: 'Uniformity of weight',
    short: 'Consistency between units',
    explanation:
      'Individual tablets, capsules or units in this batch varied in weight more than the standard allows. Consistent weight is how a batch keeps a consistent dose.',
  },
  uniformity_of_dispersion: {
    label: 'Uniformity of dispersion',
    short: 'How evenly it disperses in water',
    explanation:
      'This dispersible product did not spread evenly through water within the expected time when tested.',
  },
  density: {
    label: 'Density',
    short: 'Weight for a given volume',
    explanation:
      'A density measurement — recorded as specific gravity, relative density or weight per millilitre — fell outside the range the standard specifies.',
  },
  extractable_volume: {
    label: 'Extractable volume',
    short: 'Amount that can be drawn out',
    explanation:
      'The volume that could actually be drawn from the container did not match what the standard requires. This is checked on injections and other liquids.',
  },
  clarity_of_solution: {
    label: 'Clarity of solution',
    short: 'Appearance once dissolved',
    explanation:
      'When prepared as a solution, the appearance, clarity or colour did not match what the standard describes.',
  },
  dimensions: {
    label: 'Dimensions',
    short: 'Physical measurements',
    explanation:
      'A physical measurement such as length, diameter or thread count fell outside the specified range. This applies mainly to medical devices and dressings.',
  },
  spurious: {
    label: 'Spurious',
    short: 'Declared fake by CDSCO',
    explanation:
      'CDSCO has declared this batch spurious — meaning it is presented as a medicine it is not. In many of these cases the company named on the label has told the regulator they did not make it.',
  },
  other: {
    label: 'Other',
    short: 'Reason not matched to a known test',
    explanation:
      'CDSCO published a reason for this batch that we could not match to a standard test category. The regulator’s exact wording is shown above, unchanged — read that rather than this label.',
  },
};

export const ALL_CATEGORIES = Object.keys(FAILURE_CATEGORIES) as FailureCategory[];

export function categoryInfo(key: string): CategoryInfo {
  return (
    FAILURE_CATEGORIES[key as FailureCategory] ?? {
      label: key,
      short: 'Unrecognised category',
      explanation:
        'This category is not one MedCheck recognises. The regulator’s exact wording is shown above, unchanged.',
    }
  );
}
