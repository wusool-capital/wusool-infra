import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

// Local live mode: the Worker's /api/v1 proxy is replaced by this one, pointing at a Toolkit you run yourself.
export default defineConfig({
  plugins: [reactRouter()],
  server: { proxy: { "/api/v1": process.env.TOOLKIT_DEV_URL ?? "http://localhost:8000" } },
});
