import { describe, expect, test } from "vitest";
import { signsFromText, triage } from "./triage";

describe("triage", () => {
  test("any danger sign gives an urgent referral", () => {
    for (const sign of ["lethargy", "cannot_drink", "vomits_everything", "convulsions"] as const) {
      const result = triage({ signs: [sign], spo2: 97 });
      expect(result.outcome).toBe("urgent_referral");
      expect(result.title).toBe("Urgent referral");
    }
  });

  test("SpO2 below 90 gives an urgent referral, 90 does not", () => {
    expect(triage({ signs: ["none"], spo2: 89 })).toEqual({
      outcome: "urgent_referral",
      title: "Urgent referral",
      reason: "SpO2 is 89%, below 90%.",
    });
    expect(triage({ signs: ["none"], spo2: 90 }).outcome).toBe("no_danger_sign");
  });

  test("no sign and normal SpO2 advises a malaria test if there is fever", () => {
    const result = triage({ signs: ["none"], spo2: 97 });
    expect(result.outcome).toBe("no_danger_sign");
    expect(result.title).toBe("No danger sign found");
    expect(result.reason).toContain("rapid malaria test today");
    expect(triage({ signs: [], spo2: null }).reason).toContain("SpO2 not measured");
  });

  test("a typed answer is matched by keywords", () => {
    expect(signsFromText("very sleepy and sick")).toEqual(["lethargy"]);
    expect(signsFromText("He can't drink anything")).toEqual(["cannot_drink"]);
    expect(signsFromText("she is not drinking and throws up everything")).toEqual(["cannot_drink", "vomits_everything"]);
    expect(signsFromText("had a fit this morning")).toEqual(["convulsions"]);
    expect(signsFromText("seizures")).toEqual(["convulsions"]);
    expect(signsFromText("fitness is fine, just a cough")).toEqual([]);
    expect(signsFromText("none of these")).toEqual([]);
    const result = triage({ signs: [], answer: "very sleepy and sick", spo2: 98 });
    expect(result.outcome).toBe("urgent_referral");
    expect(result.reason).toBe("Answer mentions: very sleepy or hard to wake. Confirm with the carer.");
  });

  test("reasons list every sign found and low SpO2 together", () => {
    const result = triage({ signs: ["convulsions", "lethargy"], spo2: 85 });
    expect(result.reason).toBe("Danger sign reported: very sleepy or hard to wake, fits. SpO2 is 85%, below 90%.");
  });

  test("never words the result as a diagnosis", () => {
    const all = [triage({ signs: ["lethargy"], spo2: 80 }), triage({ signs: ["none"], spo2: 98 })];
    for (const r of all) expect(`${r.title} ${r.reason}`.toLowerCase()).not.toMatch(/diagnos|has malaria/);
  });

  test("negated mentions do not count", () => {
    for (const text of ["no fits", "not sleepy", "no vomiting", "never had convulsions", "without vomiting", "denies fits", "no vomiting or fits", "she is not very sleepy"]) {
      expect(signsFromText(text), text).toEqual([]);
    }
    expect(signsFromText("no fever but very sleepy")).toEqual(["lethargy"]);
    expect(signsFromText("no fever and very sleepy")).toEqual(["lethargy"]);
  });

  test("every common way of saying the child cannot drink is caught", () => {
    for (const text of [
      "cannot drink", "can't drink", "can\u2019t drink", "doesn't drink", "does not drink", "not able to drink",
      "isn't able to breastfeed", "unable to feed", "won't drink", "refuses to drink", "she cannot eat or drink",
    ]) {
      expect(signsFromText(text), text).toEqual(["cannot_drink"]);
    }
    expect(signsFromText("drinks well")).toEqual([]);
    expect(signsFromText("is able to drink")).toEqual([]);
  });

  test("vomiting counts only when it is everything", () => {
    expect(signsFromText("vomited once yesterday")).toEqual([]);
    expect(signsFromText("vomits everything")).toEqual(["vomits_everything"]);
    expect(signsFromText("vomiting all the time")).toEqual(["vomits_everything"]);
    expect(signsFromText("he cannot keep anything down")).toEqual(["vomits_everything"]);
    expect(signsFromText("no vomiting everything")).toEqual([]);
  });

  test("a typed sign asks to confirm, a button sign is reported", () => {
    const typed = triage({ signs: [], answer: "had fits and can't drink", spo2: null });
    expect(typed.outcome).toBe("urgent_referral");
    expect(typed.reason).toBe("Answer mentions: cannot drink, fits. Confirm with the carer.");
    const button = triage({ signs: ["convulsions"], spo2: null });
    expect(button.outcome).toBe(typed.outcome);
    expect(button.reason).toBe("Danger sign reported: fits.");
    expect(triage({ signs: [], answer: "no fits, drinks well", spo2: null }).outcome).toBe("no_danger_sign");
  });

  test("SpO2 that is not a live measurement is labelled and never drives the outcome", () => {
    expect(triage({ signs: ["none"], spo2: 97, spo2Source: "simulation" }).reason).toContain("SpO2 is 97% (simulation).");
    const low = triage({ signs: ["none"], spo2: 85, spo2Source: "replay" });
    expect(low.outcome).toBe("no_danger_sign");
    expect(low.reason).toContain("SpO2 is 85% (replay).");
    expect(triage({ signs: ["none"], spo2: null }).reason).toContain("SpO2 not measured.");
  });
});
