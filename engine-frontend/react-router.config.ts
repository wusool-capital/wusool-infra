import type { Config } from "@react-router/dev/config";

// SPA mode: the prototype has no server. Production reads come from the Toolkit API.
export default {
  ssr: false,
} satisfies Config;
