export const DANGER_SIGNS = [
  { id: "lethargy", words: "very sleepy or hard to wake" },
  { id: "cannot_drink", words: "cannot drink" },
  { id: "vomits_everything", words: "vomits everything" },
  { id: "convulsions", words: "fits" },
] as const;

export type DangerSign = (typeof DANGER_SIGNS)[number]["id"];
export type TriageOutcome = "urgent_referral" | "no_danger_sign";
export type TriageResult = { outcome: TriageOutcome; title: string; reason: string };

export const SPO2_REFERRAL_BELOW = 90;

export type Spo2Source = "replay" | "simulation";

const NEGATION = /\b(no|not|never|without|denies|denied|deny|nor|none|isn't|wasn't|hasn't|doesn't|didn't|hasnt|isnt|doesnt|didnt)\b/;
const NEGATION_REACH = 3;

// signs that are a negation themselves, so a "not" in them is the sign and not a denial
const SELF_NEGATED: Partial<Record<DangerSign, RegExp>> = {
  cannot_drink:
    /\b(?:can ?not|can'?t|won'?t|will not|unable to|refuses? to|refusing to|doesn'?t|does not|didn'?t|did not|(?:is\s+not|isn'?t|not)\s+able\s+to|not)\s+(?:\w+\s+or\s+)?(?:drink\w*|breast ?feed\w*|feed\w*)\b/,
  vomits_everything: /\b(?:can ?not|can'?t|won'?t|unable to|not able to)\s+keep\s+(?:anything|any\w*|food|it)\s+down\b/,
  lethargy: /\b(?:won'?t wake|not waking|cannot be woken|can'?t be woken)\b/,
};

const MENTIONS: Partial<Record<DangerSign, RegExp>> = {
  lethargy: /\b(sleepy|drowsy|letharg\w*|hard to wake|unconscious|floppy)\b/g,
  vomits_everything: /\b(?:vomit\w*|throw\w* up|throwing up)\b[^.,;]*?\b(?:everything|all)\b/g,
  convulsions: /\b(fits?|fitting|convuls\w*|seizures?|seizing)\b/g,
};

const CLAUSE = /[.,;:!?]|\b(?:and|but|though|although|however)\b/;

function negated(clause: string, at: number): boolean {
  const before = clause.slice(0, at).trim().split(/\s+/).filter(Boolean).slice(-NEGATION_REACH);
  return before.some((word) => NEGATION.test(word));
}

function mentioned(clause: string, id: DangerSign): boolean {
  if (SELF_NEGATED[id]?.test(clause)) return true;
  const pattern = MENTIONS[id];
  if (!pattern) return false;
  for (const match of clause.matchAll(pattern)) {
    if (!negated(clause, match.index ?? 0)) return true;
  }
  return false;
}

// keyword match on a typed answer; a denied sign does not count
export function signsFromText(text: string): DangerSign[] {
  const clauses = text.toLowerCase().replace(/[‘’]/g, "'").split(CLAUSE);
  return DANGER_SIGNS.map((sign) => sign.id).filter((id) => clauses.some((clause) => mentioned(clause, id)));
}

const wordsFor = (id: DangerSign) => DANGER_SIGNS.find((sign) => sign.id === id)!.words;
const inOrder = (signs: Set<DangerSign>) => DANGER_SIGNS.map((sign) => sign.id).filter((id) => signs.has(id));

type TriageInput = {
  signs: (DangerSign | "none")[];
  answer?: string;
  spo2: number | null;
  spo2Source?: Spo2Source;
  // disease-specific warning signs the chat asked about, in the words it used
  warnings?: string[];
  fever?: boolean;
};

export function triage(input: TriageInput): TriageResult {
  const chosen = new Set<DangerSign>(input.signs.filter((s): s is DangerSign => s !== "none"));
  const typed = new Set(signsFromText(input.answer ?? "").filter((id) => !chosen.has(id)));
  const warnings = input.warnings ?? [];
  const measured = input.spo2Source === undefined;
  const lowSpo2 = measured && input.spo2 !== null && input.spo2 < SPO2_REFERRAL_BELOW;

  if (chosen.size || typed.size || warnings.length || lowSpo2) {
    const reasons = [];
    if (chosen.size) reasons.push(`Danger sign reported: ${inOrder(chosen).map(wordsFor).join(", ")}.`);
    if (typed.size) reasons.push(`Answer mentions: ${inOrder(typed).map(wordsFor).join(", ")}. Confirm with the carer.`);
    if (warnings.length) reasons.push(`Warning sign reported: ${warnings.join(", ")}.`);
    if (lowSpo2) reasons.push(`SpO2 is ${input.spo2}%, below ${SPO2_REFERRAL_BELOW}%.`);
    return { outcome: "urgent_referral", title: "Urgent referral", reason: reasons.join(" ") };
  }

  if (input.fever !== undefined) {
    const oxygen =
      input.spo2 === null ? " SpO2 not measured." : measured ? ` SpO2 is ${input.spo2}%.` : ` SpO2 is ${input.spo2}% (${input.spo2Source}).`;
    return {
      outcome: "no_danger_sign",
      title: "No danger sign found",
      reason: input.fever ? `Fever reported, no danger sign.${oxygen} Do a rapid malaria test today.` : `No fever, no danger sign.${oxygen}`,
    };
  }

  const oxygen =
    input.spo2 === null ? "SpO2 not measured." : measured ? `SpO2 is ${input.spo2}%.` : `SpO2 is ${input.spo2}% (${input.spo2Source}).`;
  return {
    outcome: "no_danger_sign",
    title: "No danger sign found",
    reason: `No danger sign reported. ${oxygen} If there is fever, do a rapid malaria test today.`,
  };
}
