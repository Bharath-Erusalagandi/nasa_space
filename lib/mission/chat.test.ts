import { describe, expect, it } from "vitest";
import { advice, choices, outcome, reply, startChat, yesNo, type ChatState, type Input } from "./chat";
import { triage } from "./triage";

const run = (state: ChatState, inputs: Input[]) => inputs.reduce(reply, state);
const pod = (state: ChatState) => state.messages.filter((m) => m.from === "pod").map((m) => m.text);
const heard = (label: string) => ({ label, confidence: 0.87 });

describe("chat", () => {
  it("with nothing heard, it asks about fever and then the danger signs", () => {
    const s = startChat(null);
    expect(pod(s)).toEqual(["Has the patient had a fever in the last two days?"]);
    expect(choices(s).map((c) => c.words)).toEqual(["Yes", "No"]);
    const next = reply(s, { choice: "yes" });
    expect(next.fever).toBe(true);
    expect(choices(next).map((c) => c.words)).toContain("very sleepy or hard to wake");
    const done = reply(next, { choice: "none" });
    expect(done.step).toBe("done");
    expect(outcome(done)).toEqual({ answer: { sign: "none" }, findings: { fever: true, warnings: [] } });
  });

  it("a main malaria mosquito opens with the genus, then the species, then the net question", () => {
    const s = startChat({ ...heard("An. arabiensis"), genus: "Anopheles", genusConfidence: 0.94 });
    expect(pod(s)[0]).toBe(
      "I just heard a mosquito near the pod: Anopheles, the kind that carries malaria (94% sure). Most likely An. arabiensis (87%). It is one of Zambia's main malaria mosquitoes. Did the patient sleep under a mosquito net last night?",
    );
    expect(startChat({ ...heard("An. coustani"), genus: "Anopheles", genusConfidence: 0.9 }).messages[0].text).toBe(
      "I just heard a mosquito near the pod: Anopheles, the kind that carries malaria (90% sure). Most likely An. coustani (87%). Did the patient sleep under a mosquito net last night?",
    );
  });

  it("malaria: severe signs are asked even without fever, and a yes refers", () => {
    const s = run(startChat(heard("An. funestus")), [{ choice: "no" }, { choice: "no" }, { choice: "none" }]);
    expect(pod(s).at(-1)).toBe("Any dark or bloody urine, yellow eyes, fast or hard breathing, or unusual bleeding?");
    const done = reply(s, { choice: "yes" });
    const result = outcome(done)!;
    expect(result.findings.warnings).toEqual(["dark urine, yellow eyes, hard breathing or unusual bleeding"]);
    const t = triage({ signs: ["none"], spo2: null, ...result.findings });
    expect(result.answer).toEqual({ sign: "none" });
    expect(t.outcome).toBe("urgent_referral");
    expect(t.reason).toBe("Warning sign reported: dark urine, yellow eyes, hard breathing or unusual bleeding.");
    expect(advice(done, t)[0]).toMatch(/^Refer now\./);
  });

  it("malaria with fever and no danger: test first, and a net when there was none", () => {
    const done = run(startChat(heard("An. arabiensis")), [{ choice: "no" }, { choice: "yes" }, { choice: "none" }, { choice: "no" }]);
    const t = triage({ signs: ["none"], spo2: null, ...outcome(done)!.findings });
    expect(t.reason).toBe("Fever reported, no danger sign. SpO2 not measured. Do a rapid malaria test today.");
    expect(advice(done, t)).toEqual([
      "Fever: do a malaria rapid test today, before any treatment. Zambia's guidelines test every fever.",
      "Get a treated net and sleep under it every night.",
    ]);
  });

  it("dengue: symptoms and warning signs only follow a fever; advice avoids aspirin and ibuprofen", () => {
    const s = startChat(heard("Ae. aegypti"));
    expect(pod(s)[0]).toContain("It can carry dengue, chikungunya, Zika and yellow fever. This one bites in the daytime.");
    const feverish = run(s, [{ choice: "yes" }, { choice: "yes" }]);
    expect(pod(feverish).at(-1)).toBe("Any severe headache, pain behind the eyes, joint or muscle pain, or a rash?");
    const done = run(feverish, [{ choice: "yes" }, { choice: "none" }, { choice: "no" }]);
    const t = triage({ signs: ["none"], spo2: null, ...outcome(done)!.findings });
    expect(advice(done, t).join(" ")).toContain("no aspirin or ibuprofen");
    const noFever = run(s, [{ choice: "yes" }, { choice: "no" }, { choice: "none" }]);
    expect(noFever.step).toBe("done");
  });

  it("typed answers: yes and no words, a retry on anything else, danger signs by keyword", () => {
    let s = startChat(null);
    s = reply(s, { text: "maybe" });
    expect(pod(s).at(-1)).toBe("Sorry, I did not catch that. Please answer yes or no.");
    expect(s.step).toBe("fever");
    s = run(s, [{ text: "yes since yesterday" }, { text: "she cannot drink anything" }]);
    expect(outcome(s)).toEqual({ answer: { text: "she cannot drink anything" }, findings: { fever: true, warnings: [] } });
    const denied = run(startChat(null), [{ text: "no" }, { text: "no fits, not sleepy" }]);
    expect(outcome(denied)?.answer).toEqual({ sign: "none" });
  });

  it("yesNo reads common replies", () => {
    expect(yesNo("Yes")).toBe(true);
    expect(yesNo("yeah a lot")).toBe(true);
    expect(yesNo("nope")).toBe(false);
    expect(yesNo("not really")).toBe(false);
    expect(yesNo("perhaps")).toBeNull();
  });

  it("a finished chat takes no more answers", () => {
    const done = run(startChat(null), [{ choice: "no" }, { choice: "none" }]);
    expect(reply(done, { choice: "yes" })).toBe(done);
    expect(choices(done)).toEqual([]);
  });
});
