import createClient from "openapi-fetch";
import type { paths } from "./schema";

// `import.meta.env.BASE_URL` is what Vite's `base` resolves to at build time,
// so the client speaks to the same prefix the app is served from. Hard-coding
// "/" here is the mistake that works in development and 404s behind Traefik.
export const client = createClient<paths>({
  baseUrl: import.meta.env.BASE_URL,
});
