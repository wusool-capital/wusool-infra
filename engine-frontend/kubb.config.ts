import { pluginFetch } from "@kubb/plugin-fetch";
import { pluginTs } from "@kubb/plugin-ts";
import { defineConfig } from "kubb/config";

// Generated code isn't written for exactOptionalPropertyTypes; call sites stay fully checked.
const banner = "// @ts-nocheck";

// openapi.json is exported from FastAPI by server/scripts/export_openapi.py --app engine.
// Same-origin: the Worker proxies /api/v1/* and Cloudflare Access signs the user in.
export default defineConfig({
  input: "./openapi.json",
  output: { path: "./app/gen", clean: true },
  plugins: [
    pluginTs({ output: { path: "types", banner } }),
    pluginFetch({ output: { path: "clients", banner } }),
  ],
});
