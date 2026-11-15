// Placeholder until logos come from the Sanity `partner` document: the initials on a sky square.
export function PartnerLogo({ name, size = "large" }: { name: string; size?: "small" | "large" }) {
  const initials = name
    .split(/\s+/)
    .filter((word) => /^[A-Z]/.test(word))
    .slice(0, 2)
    .map((word) => word[0])
    .join("");
  return (
    <span className={`partner-logo partner-logo--${size}`} aria-hidden="true">
      {initials}
    </span>
  );
}
