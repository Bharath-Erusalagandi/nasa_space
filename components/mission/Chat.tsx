"use client";

import { RiArrowRightLine } from "@remixicon/react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { LinkButton } from "@/components/base/buttons/link-button";
import { Input } from "@/components/base/input/input";
import { advice, choices, outcome, reply, startChat, type ChatState, type Input as ChatInput } from "@/lib/mission/chat";
import { oxygenFor, session } from "@/lib/mission/session";
import { getPlace, useMission } from "@/lib/mission/state";
import { showStep } from "@/lib/mission/view";
import { listenerStore, useListener } from "@/lib/pod/listener";
import { podStore } from "@/lib/pod/store";
import { cx } from "@/utils/cx";
import { Note } from "./primitives";

// the conversation with the patient or carer: what was heard sets the questions, the answers set the triage
export function Chat() {
  const place = useMission(getPlace);
  const story = useMission((s) => s.story);
  const heard = useListener((s) => s.heard);
  const [state, setState] = useState<ChatState>(() => startChat(null));
  const [closing, setClosing] = useState<string[]>([]);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const sending = useRef(false);

  const restart = (h: typeof heard) => {
    setState(startChat(h));
    setClosing([]);
  };

  // a new mosquito starts a new conversation, unless one is under way
  useEffect(() => {
    if (!heard) return;
    setState((s) => {
      const underWay = s.step !== "done" && s.messages.some((m) => m.from === "person");
      if (underWay) return s;
      setClosing([]);
      return startChat(heard);
    });
  }, [heard]);

  // answers belong to one place; picking another starts over
  const placeId = place?.id;
  useEffect(() => {
    setState(startChat(listenerStore.getState().heard));
    setClosing([]);
  }, [placeId]);

  useEffect(() => {
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    end.current?.scrollIntoView({ block: "nearest", behavior: calm ? "auto" : "smooth" });
  }, [state.messages.length, closing.length]);

  async function send(input: ChatInput) {
    // a second tap before the first is handled would answer from a stale state
    if (sending.current || state.step === "done") return;
    const next = reply(state, input);
    setState(next);
    setText("");
    const done = outcome(next);
    if (!done) return;
    sending.current = true;
    try {
      const visit = await session.answer(done.answer, oxygenFor(podStore.getState().latest.spo2, Date.now()), done.findings);
      if (visit) setClosing(advice(next, visit.triage));
    } finally {
      sending.current = false;
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (text.trim()) void send({ text });
  }

  const options = choices(state);
  const lastPod = state.messages.findLastIndex((m) => m.from === "pod");

  return (
    <section role="group" aria-label="Conversation" className="flex min-w-0 flex-col gap-3 border-t border-separator-border pt-4">
      <header className="flex flex-col gap-0.5">
        <h3 className="text-headline-semibold text-text-primary">Patient check</h3>
        <Note>Ask the patient or carer, tap their answer. The answers decide the referral, the order and the delivery.</Note>
      </header>
      <ol className="flex flex-col gap-3" aria-live="polite">
        {state.messages.map((m, i) => (
          <li key={i} className={cx("flex", m.from === "person" ? "justify-end" : "justify-start")}>
            {m.from === "pod" ? (
              <p
                data-testid={i === lastPod && state.step !== "done" ? "question" : undefined}
                className={cx(
                  "max-w-[90%]",
                  i === lastPod && state.step !== "done" ? "text-title-3-medium text-text-primary" : "text-body-regular text-text-secondary",
                )}
              >
                {m.text}
              </p>
            ) : (
              <p data-testid="answer" className="max-w-[80%] rounded-2xl bg-background-secondary-default px-3 py-1.5 text-body-medium text-text-primary">
                {m.text}
              </p>
            )}
          </li>
        ))}
        {closing.map((line, i) => (
          <li key={`closing-${i}`} className="flex justify-start">
            <p data-testid="advice" className="max-w-[90%] text-body-medium text-text-primary">
              {line}
            </p>
          </li>
        ))}
      </ol>
      <div ref={end} />
      {options.length ? (
        <>
          <ul className="flex flex-wrap gap-2" aria-label="Answers">
            {options.map((o) => (
              <li key={o.id}>
                <Button variant="secondary" size="small" disabled={!place} onClick={() => void send({ choice: o.id })}>
                  {o.words}
                </Button>
              </li>
            ))}
          </ul>
          <form onSubmit={submit} className="flex items-end gap-2">
            <Input aria-label="Type the answer" placeholder="Or type what the patient says" value={text} onChange={setText} size="small" className="min-w-0 flex-1" />
            <Button type="submit" variant="secondary" size="small" disabled={!place || !text.trim()}>
              Send
            </Button>
          </form>
        </>
      ) : (
        <div className="flex items-center justify-between gap-4">
          <LinkButton size="small" onClick={() => restart(heard)}>
            Start over
          </LinkButton>
          {closing.length && !story ? (
            <Button variant="primary" size="small" trailingIcon={RiArrowRightLine} onClick={() => showStep("action")}>
              See the order
            </Button>
          ) : null}
        </div>
      )}
      <Note>Hearing a mosquito does not mean anyone is infected. Not a diagnosis.</Note>
    </section>
  );
}
