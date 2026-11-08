"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { describeError, getMe, loadHistory, streamMessage } from "@/lib/api";
import { useDictation, useSpeech } from "@/lib/voice";

const NOTES = {
  masked: "Personal details in this message were hidden before it reached the model.",
  blocked: "The safety filter stopped this message before it reached the model.",
  output_blocked: "The output filter withheld the model's reply.",
};

const STARTERS = [
  "I've had a long day",
  "I need to vent for a minute",
  "Help me think something through",
  "Tell me something interesting",
];

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}

let counter = 0;
const uid = () => `m${Date.now()}-${counter++}`;

export default function ChatPage() {
  const [messages, setMessages] = useState([]); // { id, role, content, note? }
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const dictation = useDictation(setInput);
  const speech = useSpeech();
  const [me, setMe] = useState(null); // { anonymous, guest_messages_left, ... }
  const refreshMe = () =>
    getMe()
      .then(setMe)
      .catch(() => {});

  useEffect(() => {
    loadHistory()
      .then((history) => setMessages(history.map((h) => ({ id: uid(), role: h.role, content: h.content }))))
      .catch((err) => setError(describeError(err)))
      .finally(() => {
        setReady(true);
        refreshMe();
      });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden"; // no scrollbar until it's needed
  }, [input]);

  async function submit() {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg = { id: uid(), role: "user", content: text };
    const replyId = uid();
    let fullText = ""; // the whole reply, kept so it can be read aloud when it is finished

    dictation.abort(); // stop listening so late words don't land in the cleared box
    speech.stop(); // stop reading the previous reply
    let started = false; // has the first piece of Nasha's reply arrived?

    setMessages((m) => [...m, userMsg]);
    setInput("");
    setError(null);
    setSending(true);

    const setReply = (change) =>
      setMessages((m) => {
        const exists = m.some((x) => x.id === replyId);
        const base = exists ? m : [...m, { id: replyId, role: "assistant", content: "" }];
        return base.map((x) => (x.id === replyId ? { ...x, ...change(x) } : x));
      });

    try {
      await streamMessage(text, (event) => {
        if (event.type === "delta") {
          started = true;
          fullText += event.text;
          setReply((x) => ({ content: x.content + event.text }));
        } else if (event.type === "replace") {
          started = true;
          fullText = event.text;
          setReply(() => ({ content: event.text }));
        } else if (event.type === "done") {
          const action = event.security_action;
          if (action === "masked" || action === "blocked") {
            setMessages((m) => m.map((x) => (x.id === userMsg.id ? { ...x, note: NOTES[action] } : x)));
          } else if (action === "output_blocked") {
            setReply(() => ({ note: NOTES.output_blocked }));
          }
          speech.speak(fullText);
          refreshMe(); // update the guest message count
        }
      });
    } catch (err) {
      // nothing was saved on the server, so take the attempt back and return the text to the box
      setMessages((m) => m.filter((x) => x.id !== userMsg.id && x.id !== replyId));
      setInput(text);
      setError(describeError(err));
      if (err?.code === "guest_limit") refreshMe();
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    submit();
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const empty = ready && messages.length === 0;
  const gated = Boolean(me?.anonymous) && me.guest_messages_left === 0;
  const guestLeft = me?.anonymous ? me.guest_messages_left : null;

  return (
    <>
      <main className={`thread${empty ? " is-empty" : ""}`}>
        {empty && (
          <section className="welcome">
            <h1>Long day? Say anything.</h1>
            <p>
              Nasha is an AI companion, not a person. What you share is tied to this browser&apos;s session, and you can
              erase all of it on the memories page.
            </p>
            <ul className="starters" aria-label="Ways to start">
              {STARTERS.map((text) => (
                <li key={text}>
                  <button
                    type="button"
                    onClick={() => {
                      setInput(text);
                      inputRef.current?.focus();
                    }}
                  >
                    {text}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div role="log" aria-live={sending ? "off" : "polite"} aria-busy={sending} aria-label="Conversation" className="log">
          {messages.map((m) => (
            <article key={m.id} className={`msg ${m.role === "user" ? "from-you" : "from-nasha"}`}>
              {m.role === "assistant" && <span className="lamp" aria-hidden="true" />}
              <div className="body">
                <p className="text">{m.content}</p>
                {m.note && (
                  <p className="note">
                    <span className="visually-hidden">Safety note: </span>
                    {m.note}
                  </p>
                )}
              </div>
            </article>
          ))}

          {sending && messages[messages.length - 1]?.role === "user" && (
            <article className="msg from-nasha" aria-label="Nasha is typing">
              <span className="lamp thinking" aria-hidden="true" />
              <div className="body">
                <p className="text muted">Thinking…</p>
              </div>
            </article>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="composer">
        {(error || dictation.error) && (
          <p role="alert" className="error">
            {error || dictation.error}
          </p>
        )}
        {gated ? (
          <div className="gate" role="region" aria-label="Sign in to continue">
            <p>
              <strong>You&apos;ve used your free messages.</strong> Create a free account to keep chatting. Your chat
              and memories come with you.
            </p>
            <Link className="button" href="/signin">
              Create account or sign in
            </Link>
          </div>
        ) : (
          <>
        <form onSubmit={onSubmit}>
          <label htmlFor="message" className="visually-hidden">
            Message to Nasha
          </label>
          <textarea
            id="message"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={dictation.listening ? "Listening…" : "Say anything…"}
            rows={1}
            maxLength={4000}
            autoFocus
          />
          {dictation.supported && (
            <button
              type="button"
              className="mic"
              aria-pressed={dictation.listening}
              aria-label={dictation.listening ? "Stop voice input" : "Start voice input"}
              onClick={() => (dictation.listening ? dictation.stop() : dictation.start(input))}
            >
              <MicIcon />
            </button>
          )}
          <button type="submit" disabled={sending || !input.trim()}>
            Send
          </button>
        </form>
        {speech.supported && (
          <div className="voice-row">
            <label className="toggle">
              <input type="checkbox" checked={speech.enabled} onChange={speech.toggle} />
              Read replies aloud
            </label>
            {speech.speaking && (
              <button type="button" className="ghost small" onClick={speech.stop}>
                Stop speaking
              </button>
            )}
          </div>
        )}
          </>
        )}
        {guestLeft > 0 && (
          <p className="fineprint guest">
            Guest mode: {guestLeft} free {guestLeft === 1 ? "message" : "messages"} left.{" "}
            <Link href="/signin">Create a free account</Link> to keep chatting.
          </p>
        )}
        <p className="fineprint">
          Emails, phone numbers and card numbers are hidden before your message reaches the model.
          {dictation.supported && " Voice input is handled by your browser's speech service, which may send audio to its provider."}
        </p>
      </footer>
    </>
  );
}