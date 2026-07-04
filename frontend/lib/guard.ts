// Client-side length guard — mirrors lambdas/shared/grading.py validate_attempt.
// This is a UX nicety only; the enforcing copy is server-side in
// debrief-grade-attempt (the API is the trust boundary, curl can skip this).
export const MIN_WORDS = 40;
export const MAX_WORDS = 300;

export function countWords(text: string): number {
  const t = text.trim();
  return t ? t.split(/\s+/).length : 0;
}

export function guardMessage(text: string): string | null {
  const words = countWords(text);
  if (words < MIN_WORDS) {
    return `Your explanation is ${words} words — we need at least ${MIN_WORDS} to grade your reasoning. What are you weighing, what are you betting on, and what would make you wrong?`;
  }
  if (words > MAX_WORDS) {
    return `Your explanation is ${words} words — please tighten it to ${MAX_WORDS} or fewer. Strong reasoning is selective: keep the trade-offs that drive your call, cut the rest.`;
  }
  return null;
}
