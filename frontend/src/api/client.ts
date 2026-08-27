import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { currentLanguage } from "../i18n";

// `import.meta.env.BASE_URL` is what Vite's `base` resolves to at build time,
// so the client speaks to the same prefix the app is served from. Hard-coding
// "/" here is the mistake that works in development and 404s behind Traefik.
export const client = createClient<paths>({
  baseUrl: import.meta.env.BASE_URL,
});

// The backend renders finding messages from Accept-Language. Without this the
// interface would be German and its error messages English.
client.use({
  onRequest({ request }) {
    request.headers.set("Accept-Language", currentLanguage());
    return request;
  },
});
