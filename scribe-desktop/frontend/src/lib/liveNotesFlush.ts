// Lets the stop flow write pending live notes before the meeting is saved,
// without threading a ref through the recording page.
let flushLiveNotesImpl: (() => Promise<void>) | null = null;

export function registerLiveNotesFlush(flush: (() => Promise<void>) | null): void {
  flushLiveNotesImpl = flush;
}

export async function flushLiveNotes(): Promise<void> {
  await flushLiveNotesImpl?.();
}
