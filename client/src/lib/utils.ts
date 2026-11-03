import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Without this, tailwind-merge reads `text-caption` as a colour and drops it next to `text-ink`.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "display-md",
            "headline",
            "card-title",
            "subhead",
            "body-lg",
            "body",
            "body-sm",
            "caption",
            "button",
            "eyebrow",
            "mono",
          ],
        },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
