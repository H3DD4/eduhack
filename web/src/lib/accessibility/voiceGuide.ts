export type VoiceGuideIntent =
  | { type: "affirmative" }
  | { type: "negative" }
  | { type: "help" }
  | { type: "repeat" }
  | { type: "disable" }
  | { type: "stop" }
  | { type: "navigate"; href: string; label: string }
  | { type: "learn"; topic: string }
  | { type: "start_topic" }
  | { type: "next" }
  | { type: "back" }
  | { type: "select"; option: string }
  | { type: "focus"; field: string }
  | { type: "type"; value: string }
  | { type: "click"; control: string }
  | { type: "submit" }
  | { type: "cancel" }
  | { type: "unknown" };

const clean = (value: string) => value.toLowerCase().trim().replace(/[.!?]+$/g, "").replace(/\s+/g, " ");

export function parseVoiceGuideIntent(input: string): VoiceGuideIntent {
  const phrase = clean(input);

  if (/^(yes|yeah|yep|sure|okay|ok|please do|turn it on|i am blind|i'm blind|i cannot read|i can't read|i need spoken help)$/.test(phrase)) {
    return { type: "affirmative" };
  }
  if (/^(no|no thanks|not now|don't|do not|leave it off|i can read|i don't need spoken help)$/.test(phrase)) {
    return { type: "negative" };
  }
  if (/^(turn off|disable|switch off) (the )?(voice guide|voice help)$/.test(phrase)) return { type: "disable" };
  if (/^(stop speaking|be quiet|silence)$/.test(phrase)) return { type: "stop" };
  if (/^(help|i need help|what can you do|what should i do next|what's next|next step|read this page( to me)?|read the next step)$/.test(phrase)) {
    return { type: "help" };
  }
  if (/^(repeat|say that again|repeat that)$/.test(phrase)) return { type: "repeat" };
  if (/^(cancel|never mind|nevermind)$/.test(phrase)) return { type: "cancel" };
  if (/^(confirm|yes confirm|confirm it)$/.test(phrase)) return { type: "affirmative" };

  const learnMatch = phrase.match(/^(?:i want to learn|teach me|help me learn|learn about|learn|i want to study|study)\s+(.+)$/);
  if (learnMatch) {
    const topic = learnMatch[1].trim().replace(/^about\s+/, "");
    if (/^(something new|a subject|a new topic)$/.test(topic)) {
      return { type: "navigate", href: "/subjects/new", label: "new subject" };
    }
    return { type: "learn", topic };
  }

  if (/^(go to |navigate to |open )?(today|home|dashboard)$/.test(phrase)) return { type: "navigate", href: "/today", label: "Today" };
  if (/^(go to |navigate to |open )?(subjects|courses|my subjects)$/.test(phrase)) return { type: "navigate", href: "/subjects", label: "Subjects" };
  if (/^(add|create|new) (a )?(subject|course)$/.test(phrase) ||
    /^(learn something new|i want to learn something new|add a subject)$/.test(phrase)) {
    return { type: "navigate", href: "/subjects/new", label: "new subject" };
  }
  if (/^(go to |navigate to |open )?(planner|study planner)$/.test(phrase)) return { type: "navigate", href: "/planner", label: "Planner" };
  if (/^(go to |navigate to |open )?(progress|my progress)$/.test(phrase)) return { type: "navigate", href: "/progress", label: "Progress" };
  if (/^(go to |navigate to |open )?(settings|my settings)$/.test(phrase)) return { type: "navigate", href: "/settings", label: "Settings" };
  if (/^(go to |navigate to |open )?(3d teachers|teachers|teacher)$/.test(phrase)) return { type: "navigate", href: "/teachers", label: "3D Teachers" };
  if (/^(sign in|log in|login|log me in)$/.test(phrase)) return { type: "navigate", href: "/welcome", label: "sign in" };
  if (/^(create an account|create account|register|sign up)$/.test(phrase)) return { type: "navigate", href: "/welcome?mode=create", label: "account creation" };

  if (/^(start learning|create topic|submit topic)$/.test(phrase)) return { type: "start_topic" };
  if (/^(next|continue|next question)$/.test(phrase)) return { type: "next" };
  if (/^(back|go back|previous)$/.test(phrase)) return { type: "back" };
  if (/^(submit|submit form|finish|save and start|confirm scope|start session)$/.test(phrase)) return { type: "submit" };

  const focusMatch = phrase.match(/^(?:focus|focus on|go to field)\s+(.+)$/);
  if (focusMatch) return { type: "focus", field: focusMatch[1].trim() };

  const typeMatch = phrase.match(/^(?:type|dictate)\s+(.+)$/);
  if (typeMatch) return { type: "type", value: typeMatch[1].trim() };

  const clickMatch = phrase.match(/^(?:click|press|activate)\s+(.+)$/);
  if (clickMatch) return { type: "click", control: clickMatch[1].trim() };

  const selectMatch = phrase.match(/^(?:choose|select)\s+(.+)$/);
  if (selectMatch) return { type: "select", option: selectMatch[1].trim() };

  return { type: "unknown" };
}

export function voiceGuidePagePrompt(pathname: string, search = ""): string {
  const params = new URLSearchParams(search);
  const topic = params.get("topic")?.trim();
  const withReplyInstruction = (text: string) =>
    `${text} You can also say focus followed by a field, type followed by text, choose an option, click a control, next, back, or submit. I will confirm actions that change data. Press Ask by voice when you are ready; the microphone is not always listening.`;
  if (pathname === "/welcome") {
    if (params.get("mode") === "create") {
      return withReplyInstruction("This is the create-account form. Say focus email, then type your email. Type your password or use a password manager; do not speak passwords. Say submit when ready.");
    }
    return withReplyInstruction("Welcome to ThinkFirst. I can guide you by voice. Say help for voice commands. For sign in, use your password manager or type your password; do not speak it aloud.");
  }
  if (pathname === "/onboarding") {
    return withReplyInstruction("You are in setup. I can read each question and help choose an answer. Say choose followed by an option, next, or back.");
  }
  if (pathname === "/subjects/new") {
    return topic
      ? withReplyInstruction(`The topic form is open with ${topic} entered. Say start learning when you are ready, or say cancel.`)
      : withReplyInstruction("This is the new subject page. You can say, I want to learn, followed by a topic. For course files, choose files manually.");
  }
  if (pathname === "/subjects") return withReplyInstruction("This is your subjects page. Say add a subject to start a new one, or say today to return to your study dashboard.");
  if (pathname === "/today") return withReplyInstruction("This is your study dashboard. Say add a subject, planner, progress, settings, or help.");
  if (pathname === "/planner") return withReplyInstruction("This is your planner. Say today, subjects, progress, settings, or help to move around.");
  if (pathname === "/progress") return withReplyInstruction("This is your progress page. Say subjects, planner, today, settings, or help.");
  if (pathname === "/settings") return withReplyInstruction("This is settings. You can change your preferences here. Say today, subjects, planner, or help.");
  if (pathname === "/teachers") return withReplyInstruction("This is the 3D teachers page. Choose a teacher to hear them speak, or say today, subjects, or help.");
  if (pathname.startsWith("/subjects/")) {
    if (/^\/subjects\/[^/]+\/sessions\/[^/]+\/setup$/.test(pathname)) {
      return withReplyInstruction("Review the session settings. Say choose text or voice, then say start session when ready. I will ask you to confirm before starting.");
    }
    if (/^\/subjects\/[^/]+\/setup$/.test(pathname)) {
      return withReplyInstruction("Review your subject setup. For a guided topic, say start learning. For course files, review the proposed scope and say confirm scope. I will ask you to confirm before continuing.");
    }
    if (/^\/subjects\/[^/]+\/roadmap/.test(pathname)) {
      return withReplyInstruction("This is your learning roadmap. Say help for navigation, or say today, subjects, planner, or progress.");
    }
    return withReplyInstruction("You are in a subject. Say help to hear the main actions, or say today, subjects, planner, or progress.");
  }
  return withReplyInstruction("I can help you move around ThinkFirst. Say help to hear the available voice commands.");
}
