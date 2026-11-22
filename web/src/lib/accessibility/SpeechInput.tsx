"use client";

import { useEffect, useRef, useState } from "react";
import { browserSTTProvider } from "./profile";

export function SpeechInput({ language, onTranscript }: { language: string; onTranscript: (text: string) => void }) {
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState("");
  const recognition = useRef<ReturnType<typeof browserSTTProvider.create>>(null);

  useEffect(() => () => recognition.current?.stop(), []);

  const toggle = () => {
    if (recording) {
      recognition.current?.stop();
      return;
    }
    const instance = browserSTTProvider.create();
    if (!instance) {
      setStatus("Dictation is not available in this browser. You can continue typing.");
      return;
    }
    instance.lang = language;
    instance.interimResults = false;
    instance.onstart = () => {
      setRecording(true);
      setStatus("Listening. Your transcript will be added to the field so you can review and edit it.");
    };
    instance.onresult = (event) => {
      const transcript = Array.from(event.results, (result) => result[0]?.transcript || "").join(" ").trim();
      if (transcript) onTranscript(transcript);
    };
    instance.onerror = (event) => {
      setStatus(event.error === "not-allowed"
        ? "Microphone permission was not granted. You can continue typing."
        : "Dictation stopped before a transcript was ready. You can continue typing.");
    };
    instance.onend = () => setRecording(false);
    recognition.current = instance;
    setStatus("Starting dictation…");
    try {
      instance.start();
    } catch {
      setRecording(false);
      setStatus("Dictation could not start. You can continue typing.");
    }
  };

  return (
    <div className="mt-2">
      <button type="button" className={`btn-secondary !min-h-[40px] !px-3 text-meta ${recording ? "!bg-hl" : ""}`}
        onClick={toggle} aria-pressed={recording}>
        {recording ? "Stop dictation" : "Dictate"}
      </button>
      <p className="text-meta text-ink-muted" role="status" aria-live="polite">{status}</p>
    </div>
  );
}
