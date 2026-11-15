// A scripted conversation, no language model: what was heard sets the questions, the answers set the triage.
// Wording follows WHO fact sheets (malaria, dengue, West Nile virus), WHO IMCI and Zambia's malaria guidelines;
// the sources are in docs/REFERENCES.md.
import { speciesFor, type VectorGroup } from "@/lib/pod/species";
import { DANGER_SIGNS, signsFromText, type DangerSign, type TriageResult } from "./triage";
import type { Answer, Findings } from "./session";

export type Heard = { label: string; confidence: number; via: "microphone" | "recording"; genus?: string; genusConfidence?: number };

type Step = "bites" | "fever" | "symptoms" | "danger" | "warning" | "done";

export type Message = { from: "pod" | "person"; text: string };
export type Choice = { id: string; words: string };

export type ChatState = {
  heard: Heard | null;
  group: VectorGroup | null;
  step: Step;
  messages: Message[];
  bites: boolean | null;
  fever: boolean | null;
  sign: DangerSign | "none" | null;
  typed: string | null;
  warnings: string[];
};

const WARNINGS: Record<VectorGroup, { words: string; ask: string } | null> = {
  anopheles: { words: "dark urine, yellow eyes, hard breathing or unusual bleeding", ask: "Any dark or bloody urine, yellow eyes, fast or hard breathing, or unusual bleeding?" },
  aedes: { words: "belly pain, repeated vomiting or bleeding", ask: "Any severe belly pain, vomiting again and again, bleeding gums or nose, or blood in vomit or stool?" },
  culex: { words: "stiff neck, confusion or new weakness", ask: "Any stiff neck, confusion, or new weakness in the arms or legs?" },
  mansonia: null,
};

const BITES: Record<VectorGroup, string> = {
  anopheles: "Did the patient sleep under a mosquito net last night?",
  aedes: "This one bites in the daytime. Has the patient been bitten during the day this week?",
  culex: "Has the patient been bitten a lot at night this week?",
  mansonia: "Has the patient been bitten a lot at night this week?",
};

const FEVER = "Has the patient had a fever in the last two days?";
const DENGUE_SYMPTOMS = "Any severe headache, pain behind the eyes, joint or muscle pain, or a rash?";
export const DANGER_QUESTION = "Is the patient very sleepy or hard to wake, unable to drink, vomiting everything, or having fits?";

const YES_NO: Choice[] = [
  { id: "yes", words: "Yes" },
  { id: "no", words: "No" },
];

const pct = (x: number) => `${Math.round(x * 100)}%`;

function opening(heard: Heard | null): string {
  if (!heard) return FEVER;
  const species = speciesFor(heard.label);
  const genus = heard.genus ?? heard.label;
  const sure = pct(heard.genusConfidence ?? heard.confidence);
  const where = heard.via === "microphone" ? "I just heard a mosquito near the pod" : "This recording is a mosquito";
  if (!species) return `${where}: ${heard.label} (${sure} sure). ${FEVER}`;
  const likely = `Most likely ${heard.label} (${pct(heard.confidence)}).`;
  if (species.group === "anopheles") {
    const kind = species.primaryMalaria ? `${likely} It is one of Zambia's main malaria mosquitoes.` : likely;
    return `${where}: ${genus}, the kind that carries malaria (${sure} sure). ${kind} ${BITES.anopheles}`;
  }
  const carries =
    species.group === "aedes"
      ? "It can carry dengue, chikungunya, Zika and yellow fever."
      : species.group === "culex"
        ? "It can carry West Nile virus and filariasis."
        : "It can carry filariasis.";
  return `${where}: ${genus} (${sure} sure). ${likely} ${carries} ${BITES[species.group]}`;
}

export function startChat(heard: Heard | null): ChatState {
  const group = speciesFor(heard?.label)?.group ?? null;
  return {
    heard,
    group,
    step: group ? "bites" : "fever",
    messages: [{ from: "pod", text: opening(heard) }],
    bites: null,
    fever: null,
    sign: null,
    typed: null,
    warnings: [],
  };
}

export function choices(state: ChatState): Choice[] {
  if (state.step === "done") return [];
  if (state.step === "danger") return [...DANGER_SIGNS.map((s) => ({ id: s.id, words: s.words })), { id: "none", words: "none of these" }];
  return YES_NO;
}

const YES = /^(y|yes|yeah|yep|yup|ya|ndi|eya|ee|she did|he did|she has|he has|they have|true|a lot|many)\b/i;
const NO = /^(n|no|nope|nah|not|never|none|ayi|she didn'?t|he didn'?t|hasn'?t|didn'?t|false)\b/i;

export function yesNo(text: string): boolean | null {
  const t = text.trim();
  if (YES.test(t)) return true;
  if (NO.test(t)) return false;
  return null;
}

function nextAfterFever(state: ChatState): Step {
  return state.fever && state.group === "aedes" ? "symptoms" : "danger";
}

function nextAfterDanger(state: ChatState): Step {
  const warning = state.group ? WARNINGS[state.group] : null;
  if (!warning) return "done";
  // the dengue and West Nile warning signs follow a fever; the severe malaria signs are asked either way
  return state.group === "anopheles" || state.fever ? "warning" : "done";
}

function question(state: ChatState, step: Step): string | null {
  if (step === "fever") return FEVER;
  if (step === "symptoms") return DENGUE_SYMPTOMS;
  if (step === "danger") return DANGER_QUESTION;
  if (step === "warning" && state.group) return WARNINGS[state.group]?.ask ?? null;
  return null;
}

function moveTo(state: ChatState, step: Step, said: string): ChatState {
  const messages: Message[] = [...state.messages, { from: "person", text: said }];
  const ask = question(state, step);
  if (ask) messages.push({ from: "pod", text: ask });
  return { ...state, step, messages };
}

const retry = (state: ChatState, said: string): ChatState => ({
  ...state,
  messages: [...state.messages, { from: "person", text: said }, { from: "pod", text: "Sorry, I did not catch that. Please answer yes or no." }],
});

export type Input = { choice: string } | { text: string };

export function reply(state: ChatState, input: Input): ChatState {
  if (state.step === "done") return state;
  const said = "text" in input ? input.text.trim() : (choices(state).find((c) => c.id === input.choice)?.words ?? input.choice);
  if (!said) return state;

  if (state.step === "danger") {
    if ("choice" in input) {
      const sign = input.choice as DangerSign | "none";
      const next = { ...state, sign };
      return moveTo(next, nextAfterDanger(next), said);
    }
    const found = signsFromText(said);
    const denied = found.length === 0 && yesNo(said) === false;
    const next = { ...state, sign: found[0] ?? (denied ? "none" : null), typed: found.length || denied ? null : said };
    if (found.length) next.typed = said;
    return moveTo(next, nextAfterDanger(next), said);
  }

  const answer = "choice" in input ? input.choice === "yes" : yesNo(said);
  if (answer === null) return retry(state, said);

  if (state.step === "bites") return moveTo({ ...state, bites: answer }, "fever", said);
  if (state.step === "fever") {
    const next = { ...state, fever: answer };
    return moveTo(next, nextAfterFever(next), said);
  }
  if (state.step === "symptoms") return moveTo(state, "danger", said);
  if (state.step === "warning" && state.group) {
    const warning = WARNINGS[state.group];
    const next = { ...state, warnings: answer && warning ? [warning.words] : [] };
    return moveTo(next, "done", said);
  }
  return state;
}

// what the session needs once the questions are over
export function outcome(state: ChatState): { answer: Answer; findings: Findings } | null {
  if (state.step !== "done") return null;
  const answer: Answer = state.typed ? { text: state.typed } : { sign: state.sign ?? "none" };
  return { answer, findings: { fever: state.fever ?? false, warnings: state.warnings } };
}

// the closing advice, after triage has run
export function advice(state: ChatState, result: TriageResult): string[] {
  if (result.outcome === "urgent_referral") return [`Refer now. ${result.reason} Referral transport is ordered.`];
  const lines: string[] = [];
  if (state.fever) {
    lines.push("Fever: do a malaria rapid test today, before any treatment. Zambia's guidelines test every fever.");
    if (state.group === "aedes") {
      lines.push(
        "If the test is negative, dengue is possible: paracetamol for pain, plenty to drink, no aspirin or ibuprofen. Come back at once if belly pain, repeated vomiting or bleeding start, often as the fever goes.",
      );
    }
  } else {
    lines.push("No fever and no danger sign, so no test is needed now.");
  }
  if (state.group === "anopheles") lines.push(state.bites === false ? "Get a treated net and sleep under it every night." : "Keep sleeping under a treated net every night.");
  if (state.group === "aedes") lines.push("Cover, empty and clean water containers every week; this mosquito breeds in them.");
  if (state.group === "culex" || state.group === "mansonia") lines.push("Sleep under a net to cut night bites.");
  return lines;
}
