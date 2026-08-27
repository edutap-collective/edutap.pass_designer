import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import "./i18n";

const GET = vi.fn();
vi.mock("./api/client", () => ({
  client: { GET: (...args: unknown[]) => GET(...args) },
}));

function renderApp() {
  // Retries off: the default backoff would make a failing query stay
  // "pending" for several seconds inside the test, and the whole point of
  // this test is to observe the error state promptly.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

const FAMILIES = [
  { family_id: "loyalty", label: "Loyalty", head_fields: [], required_on_create: [] },
];

describe("App error handling", () => {
  it("shows a load-failed message, not an eternal Loading…, when the catalogue query errors", async () => {
    // Reproduces Fix 4: a malformed catalogue on disk makes GET /catalogue
    // fail. Before the fix, `!catalogue.data` is also true while a query is
    // merely pending, so App.tsx could not tell the two apart and showed
    // "Loading…" forever.
    GET.mockImplementation(async (path: string) => {
      if (path === "/designer/v1/catalogue") {
        return { data: undefined, error: { detail: "catalogue at ... is malformed" } };
      }
      if (path === "/designer/v1/families") {
        return { data: FAMILIES, error: undefined };
      }
      if (path === "/designer/v1/personas") {
        return { data: [], error: undefined };
      }
      throw new Error(`unexpected path in test: ${path}`);
    });

    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /loading failed|laden fehlgeschlagen/i,
    );
    expect(screen.queryByText(/^loading…$|^wird geladen…$/i)).not.toBeInTheDocument();
  });

  it("still renders the editor once every query succeeds", async () => {
    GET.mockImplementation(async (path: string) => {
      if (path === "/designer/v1/catalogue") return { data: [], error: undefined };
      if (path === "/designer/v1/families") return { data: FAMILIES, error: undefined };
      if (path === "/designer/v1/personas") return { data: [], error: undefined };
      throw new Error(`unexpected path in test: ${path}`);
    });

    renderApp();

    expect(await screen.findByRole("button", { name: /add module|Modul hinzufügen/i })).toBeInTheDocument();
  });
});
