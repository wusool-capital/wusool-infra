'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import { Send } from 'lucide-react';

import { Dialog, DialogContent, DialogFooter, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { canSubmitFeedback, FEEDBACK_CATEGORIES, isFeedbackConfigured, MAX_FEEDBACK_CHARS, submitFeedback } from '@/lib/feedback';

interface PushConfig {
  server_url: string;
  api_key: string;
  install_id: string;
}

interface FeedbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Sends feedback through the Scribe server (see `submit_feedback`,
 * `src-tauri/src/feedback/mod.rs`) -- the same destination the Push
 * settings configure, so an unconfigured server_url/api_key blocks
 * feedback the same way it blocks a push.
 */
export function FeedbackDialog({ open, onOpenChange }: FeedbackDialogProps) {
  const router = useRouter();
  const [checkingConfig, setCheckingConfig] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [category, setCategory] = useState('');
  const [message, setMessage] = useState('');
  const [contact, setContact] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    // Guards against a rapid close-then-reopen: if this effect's own check
    // is superseded before it resolves, its result must not overwrite
    // whatever the newer (or current) check already set.
    let cancelled = false;
    setCheckingConfig(true);
    invoke<PushConfig>('get_push_config')
      .then((config) => {
        if (!cancelled) setConfigured(isFeedbackConfigured(config));
      })
      .catch(() => {
        if (!cancelled) setConfigured(false);
      })
      .finally(() => {
        if (!cancelled) setCheckingConfig(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const resetForm = () => {
    setCategory('');
    setMessage('');
    setContact('');
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitFeedback({ category, message: message.trim(), contact: contact.trim() });
      toast.success('Thanks — feedback sent');
      resetForm();
      onOpenChange(false);
    } catch (error) {
      toast.error('Could not send feedback', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const goToSettings = () => {
    onOpenChange(false);
    router.push('/settings');
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && submitting) return;
        onOpenChange(next);
      }}
    >
      <DialogContent
        className="sm:max-w-[480px]"
        onInteractOutside={(e) => submitting && e.preventDefault()}
      >
        <DialogTitle>Send feedback</DialogTitle>

        {checkingConfig ? (
          <div className="py-6 text-sm text-muted-foreground">Checking configuration…</div>
        ) : !configured ? (
          <div className="py-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Feedback is sent through your Scribe server. Add a Push destination in Settings to
              enable it.
            </p>
            <Button onClick={goToSettings} size="sm">
              Open Settings
            </Button>
          </div>
        ) : (
          <>
            <div className="space-y-4 py-2">
              <div>
                <Label htmlFor="feedback-category" className="mb-1 block">
                  Category
                </Label>
                <Select value={category} onValueChange={setCategory} disabled={submitting}>
                  <SelectTrigger id="feedback-category">
                    <SelectValue placeholder="What kind of feedback is this?" />
                  </SelectTrigger>
                  <SelectContent>
                    {FEEDBACK_CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <div className="mb-1 flex items-center justify-between">
                  <Label htmlFor="feedback-message">Message</Label>
                  <span
                    className={
                      message.length > MAX_FEEDBACK_CHARS
                        ? 'text-xs text-destructive'
                        : 'text-xs text-muted-foreground'
                    }
                  >
                    {message.length}/{MAX_FEEDBACK_CHARS}
                  </span>
                </div>
                <Textarea
                  id="feedback-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="What happened, or what would you like to see?"
                  rows={5}
                  disabled={submitting}
                />
              </div>

              <div>
                <Label htmlFor="feedback-contact" className="mb-1 block">
                  Email or name (optional)
                </Label>
                <Input
                  id="feedback-contact"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder="So we can follow up"
                  disabled={submitting}
                  maxLength={200}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                onClick={handleSubmit}
                disabled={!canSubmitFeedback({ category, message, submitting })}
                size="sm"
              >
                {submitting ? (
                  <Spinner className="mr-2 h-4 w-4" />
                ) : (
                  <Send className="w-4 h-4 mr-1" />
                )}
                {submitting ? 'Sending…' : 'Send feedback'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
