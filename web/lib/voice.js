"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SpeechRecognitionApi = () =>
  typeof window === "undefined" ? null : window.SpeechRecognition || window.webkitSpeechRecognition || null;

const DICTATION_ERRORS = {
  "not-allowed": "Microphone access is blocked. Allow it in your browser's site settings, then try again.",
  "service-not-allowed": "Voice input isn't allowed in this browser.",
  "no-speech": "Didn't catch anything. Try again.",
  "audio-capture": "No microphone found.",
  network: "Voice input needs an internet connection.",
};


export function useDictation(onTranscript) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const recRef = useRef(null);
  const baseRef = useRef("");
  const callbackRef = useRef(onTranscript);
  callbackRef.current = onTranscript;

  useEffect(() => {
    setSupported(Boolean(SpeechRecognitionApi()));
    return () => recRef.current?.abort();
  }, []);

  const start = useCallback((currentText) => {
    const Recognition = SpeechRecognitionApi();
    if (!Recognition) return;

    const rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    baseRef.current = currentText ? `${currentText.trimEnd()} ` : "";

    rec.onresult = (event) => {
      let heard = "";
      for (let i = 0; i < event.results.length; i++) heard += event.results[i][0].transcript;
      callbackRef.current(baseRef.current + heard);
    };
    rec.onerror = (event) => {
      setError(DICTATION_ERRORS[event.error] ?? "Voice input stopped unexpectedly.");
      setListening(false);
    };
    rec.onend = () => setListening(false);

    setError(null);
    try {
      rec.start();
      recRef.current = rec;
      setListening(true);
    } catch {
      setError("Voice input couldn't start. Try again.");
    }
  }, []);

  const stop = useCallback(() => recRef.current?.stop(), []);

  const abort = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    rec.onresult = null;
    rec.abort();
    setListening(false);
  }, []);

  return { supported, listening, error, start, stop, abort };
}

const STORAGE_KEY = "nasha_read_aloud";

function toChunks(text) {
  return text.match(/[^.!?\n]+[.!?]*\s*/g)?.map((c) => c.trim()).filter(Boolean) ?? [text];
}

export function useSpeech() {
  const [supported, setSupported] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const enabledRef = useRef(false);
  const generationRef = useRef(0);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return undefined;
    setSupported(true);
    try {
      const saved = localStorage.getItem(STORAGE_KEY) === "1";
      enabledRef.current = saved;
      setEnabled(saved);
    } catch {
    }
    return () => window.speechSynthesis.cancel();
  }, []);

  const stop = useCallback(() => {
    if (!("speechSynthesis" in window)) return;
    generationRef.current += 1; 
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  const toggle = useCallback(() => {
    const next = !enabledRef.current;
    enabledRef.current = next;
    setEnabled(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
    }
    if (!next) stop();
  }, [stop]);

  const speak = useCallback(
    (text) => {
      if (!enabledRef.current || !("speechSynthesis" in window) || !text?.trim()) return;
      stop();
      const generation = generationRef.current;
      const chunks = toChunks(text);
      let remaining = chunks.length;
      const finished = () => {
        remaining -= 1;
        if (remaining <= 0 && generation === generationRef.current) setSpeaking(false);
      };
      setSpeaking(true);
      for (const chunk of chunks) {
        const utterance = new SpeechSynthesisUtterance(chunk);
        utterance.lang = navigator.language || "en-US";
        utterance.onend = finished;
        utterance.onerror = finished;
        window.speechSynthesis.speak(utterance);
      }
    },
    [stop],
  );

  return { supported, enabled, speaking, toggle, speak, stop };
}