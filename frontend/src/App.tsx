import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { client } from "./api/client";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { FrontRows } from "./components/FrontRows";
import { HeadFields } from "./components/HeadFields";
import { ModuleList } from "./components/ModuleList";
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

  if (!loyalty || !catalogue.data) return <p>{t("app.loading")}</p>;

  return (
    <main>
      <header>
        <h1>{t("app.title")}</h1>
        <LanguageSwitcher />
      </header>

      <div className="editor">
        <form onSubmit={(e) => e.preventDefault()}>
          {/* The tabs will grow to three. Today there is one, and the module
              list sits OUTSIDE them — the front, the back and the overview row
              all reference the same modules. */}
          <section aria-label={t("tabs.front")}>
            <HeadFields fields={loyalty.head_fields} />
            <FrontRows />
          </section>

          <ModuleList catalogue={catalogue.data} />
        </form>

        <aside>
          <label>
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

          <Card persona={selectedPersona} />
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
