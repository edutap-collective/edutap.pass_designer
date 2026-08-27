import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { client } from "./api/client";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { FrontRows } from "./components/FrontRows";
import { HeadFields } from "./components/HeadFields";
import { ModuleList } from "./components/ModuleList";
import { Toolbar } from "./components/Toolbar";
import { DraftProvider } from "./draft/context";
import { Card } from "./preview/Card";

function Editor() {
  const { t } = useTranslation();

  const families = useQuery({
    queryKey: ["families"],
    queryFn: async () => {
      const { data, error } = await client.GET("/designer/v1/families");
      if (error) throw new Error("families failed");
      return data;
    },
  });

  const catalogue = useQuery({
    queryKey: ["catalogue"],
    queryFn: async () => {
      const { data, error } = await client.GET("/designer/v1/catalogue");
      if (error) throw new Error("catalogue failed");
      return data;
    },
  });

  const personas = useQuery({
    queryKey: ["personas"],
    queryFn: async () => {
      const { data, error } = await client.GET("/designer/v1/personas");
      if (error) throw new Error("personas failed");
      return data;
    },
  });

  // Loyalty is the only registered family; the six others need a backend round
  // first. Reading it from the list rather than hard-coding the head fields
  // means that round costs no change here.
  const loyalty = families.data?.find((f) => f.family_id === "loyalty");

  // An unselected persona_id falls back to the first persona in the list, so
  // the preview shows a card from the moment personas load — no separate
  // "nothing chosen yet" state to design for.
  const [personaId, setPersonaId] = useState("");
  const selectedPersona =
    personas.data?.find((p) => p.persona_id === personaId) ?? personas.data?.[0];

  // isError, not just "no data yet": a permanently pending query and a failed
  // one both leave `.data` undefined, and only `isError` tells them apart. A
  // malformed catalogue on disk (a `500` — see `/catalogue`'s error handling)
  // must not read forever as "Loading…".
  if (families.isError || catalogue.isError || personas.isError) {
    return <p role="alert">{t("app.loadFailed")}</p>;
  }

  if (!loyalty || !catalogue.data) return <p>{t("app.loading")}</p>;

  return (
    <main className="page">
      <header className="page__header">
        <h1 className="page__title">{t("app.title")}</h1>
        <LanguageSwitcher />
      </header>

      <div className="editor">
        <form className="editor__form" onSubmit={(e) => e.preventDefault()}>
          {/* The tabs will grow to three. Today there is one, and the module
              list sits OUTSIDE them — the front, the back and the overview row
              all reference the same modules. */}
          <section className="editor__tab" aria-label={t("tabs.front")}>
            <HeadFields fields={loyalty.head_fields} />
            <FrontRows />
          </section>

          <ModuleList catalogue={catalogue.data} />
          <Toolbar />
        </form>

        <aside className="preview">
          <label className="field preview__persona">
            {t("preview.persona")}
            <select
              value={selectedPersona?.persona_id ?? ""}
              onChange={(e) => setPersonaId(e.target.value)}
            >
              {personas.data?.map((persona) => (
                <option key={persona.persona_id} value={persona.persona_id}>
                  {persona.label}
                </option>
              ))}
            </select>
          </label>

          <div className="preview__stage">
            <Card persona={selectedPersona} />
          </div>
        </aside>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <DraftProvider>
      <Editor />
    </DraftProvider>
  );
}
