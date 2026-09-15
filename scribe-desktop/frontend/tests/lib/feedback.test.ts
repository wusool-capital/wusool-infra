import { beforeEach, describe, expect, mock, test } from "bun:test";

const invokeMock = mock(async () => null);

mock.module("@tauri-apps/api/core", () => ({
  invoke: invokeMock,
}));

describe("canSubmitFeedback", () => {
  test("false when category is empty", async () => {
    const { canSubmitFeedback } = await import("../../src/lib/feedback");
    expect(
      canSubmitFeedback({ category: "", message: "hello", submitting: false }),
    ).toBe(false);
  });

  test("false when message is empty", async () => {
    const { canSubmitFeedback } = await import("../../src/lib/feedback");
    expect(
      canSubmitFeedback({ category: "bug", message: "", submitting: false }),
    ).toBe(false);
  });

  test("false when message is whitespace only", async () => {
    const { canSubmitFeedback } = await import("../../src/lib/feedback");
    expect(
      canSubmitFeedback({ category: "bug", message: "   \n  ", submitting: false }),
    ).toBe(false);
  });

  test("false when submitting", async () => {
    const { canSubmitFeedback } = await import("../../src/lib/feedback");
    expect(
      canSubmitFeedback({ category: "bug", message: "hello", submitting: true }),
    ).toBe(false);
  });

  test("false when message exceeds the max length", async () => {
    const { canSubmitFeedback, MAX_FEEDBACK_CHARS } = await import(
      "../../src/lib/feedback"
    );
    expect(
      canSubmitFeedback({
        category: "bug",
        message: "a".repeat(MAX_FEEDBACK_CHARS + 1),
        submitting: false,
      }),
    ).toBe(false);
  });

  test("true for a valid submission", async () => {
    const { canSubmitFeedback } = await import("../../src/lib/feedback");
    expect(
      canSubmitFeedback({ category: "bug", message: "Something broke", submitting: false }),
    ).toBe(true);
  });
});

describe("isFeedbackConfigured", () => {
  test("false when server_url is empty", async () => {
    const { isFeedbackConfigured } = await import("../../src/lib/feedback");
    expect(isFeedbackConfigured({ server_url: "", api_key: "key" })).toBe(false);
  });

  test("false when server_url is whitespace", async () => {
    const { isFeedbackConfigured } = await import("../../src/lib/feedback");
    expect(isFeedbackConfigured({ server_url: "   ", api_key: "key" })).toBe(false);
  });

  test("false when api_key is empty", async () => {
    const { isFeedbackConfigured } = await import("../../src/lib/feedback");
    expect(
      isFeedbackConfigured({ server_url: "https://scribe.example.com", api_key: "" }),
    ).toBe(false);
  });

  test("true when both are present", async () => {
    const { isFeedbackConfigured } = await import("../../src/lib/feedback");
    expect(
      isFeedbackConfigured({ server_url: "https://scribe.example.com", api_key: "key" }),
    ).toBe(true);
  });
});

describe("submitFeedback", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  test("invokes submit_feedback with the exact arg keys the Rust command expects", async () => {
    const { submitFeedback } = await import("../../src/lib/feedback");
    invokeMock.mockResolvedValueOnce(null);

    await submitFeedback({ category: "bug", message: "It crashed", contact: "me@example.com" });

    expect(invokeMock).toHaveBeenCalledWith("submit_feedback", {
      category: "bug",
      message: "It crashed",
      contact: "me@example.com",
    });
  });
});
