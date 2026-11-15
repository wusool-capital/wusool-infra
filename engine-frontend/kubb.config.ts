import { pluginClient } from "@kubb/plugin-client";
import { pluginTs } from "@kubb/plugin-ts";
import { defineConfig } from "kubb/config";

// Generated code isn't written for exactOptionalPropertyTypes; call sites stay fully checked.
const banner = "// @ts-nocheck";

// openapi.json is exported from FastAPI by server/scripts/export_openapi.py --app engine.
export default defineConfig({
  input: "./openapi.json",
  output: { path: "./app/gen", clean: true },
  plugins: [
    pluginTs({ output: { path: "types", banner } }),
    pluginClient({
      output: { path: "clients", banner },
      // Relative: Vite has no `~` alias here.
      importPath: "../../lib/api-client",
    }),
  ],
});
