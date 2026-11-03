import { pluginClient } from "@kubb/plugin-client";
import { pluginReactQuery } from "@kubb/plugin-react-query";
import { pluginTs } from "@kubb/plugin-ts";
import { pluginZod } from "@kubb/plugin-zod";
import { defineConfig } from "kubb/config";

// Generated code isn't written for exactOptionalPropertyTypes; call sites stay fully checked.
const banner = "// @ts-nocheck";

// openapi.json is exported from FastAPI by server/scripts/export_openapi.py.
export default defineConfig({
  input: "./openapi.json",
  output: { path: "./src/gen", clean: true },
  plugins: [
    pluginTs({ output: { path: "types", banner } }),
    pluginZod({ output: { path: "zod", banner } }),
    pluginClient({
      output: { path: "clients", banner },
      importPath: "@/lib/api-client",
      validator: { response: "zod" },
    }),
    pluginReactQuery({ output: { path: "hooks", banner }, client: "client", hooks: true }),
  ],
});
