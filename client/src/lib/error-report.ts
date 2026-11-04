// What a developer needs from a pasted error: the message, where, and when.
export function errorReport(message: string, now: Date = new Date()): string {
  return [
    message,
    `Page: ${window.location.href}`,
    `Time: ${now.toISOString()}`,
  ].join("\n");
}
