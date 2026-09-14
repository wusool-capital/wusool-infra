// Pure helpers for the in-app feedback form -- extracted from
// FeedbackDialog so they can be unit-tested without a DOM harness. The
// Rust command (`src-tauri/src/feedback/mod.rs::submit_feedback`) mirrors
// these caps and does its own validation too -- never trust the client
// alone.

import { invoke } from '@tauri-apps/api/core';

export const MAX_FEEDBACK_CHARS = 4000;

export const FEEDBACK_CATEGORIES = [
  { value: 'bug', label: 'Bug' },
  { value: 'feature_request', label: 'Feature request' },
  { value: 'transcription_quality', label: 'Transcription quality' },
  { value: 'other', label: 'Other' },
] as const;

export type FeedbackCategory = (typeof FEEDBACK_CATEGORIES)[number]['value'];

export function canSubmitFeedback(form: {
  category: string;
  message: string;
  submitting: boolean;
}): boolean {
  if (form.submitting) return false;
  if (!form.category) return false;
  const trimmed = form.message.trim();
  if (trimmed.length === 0) return false;
  if (form.message.length > MAX_FEEDBACK_CHARS) return false;
  return true;
}

export function isFeedbackConfigured(config: { server_url: string; api_key: string }): boolean {
  return config.server_url.trim().length > 0 && config.api_key.trim().length > 0;
}

export async function submitFeedback(args: {
  category: string;
  message: string;
  contact: string;
}): Promise<void> {
  await invoke('submit_feedback', {
    category: args.category,
    message: args.message,
    contact: args.contact,
  });
}
