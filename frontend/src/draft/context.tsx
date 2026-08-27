import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from "react";
import type { Draft } from "../api/types";
import { draftReducer, emptyDraft, type DraftAction } from "./reducer";

const DraftContext = createContext<Draft | null>(null);
const DispatchContext = createContext<Dispatch<DraftAction> | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, dispatch] = useReducer(draftReducer, emptyDraft("loyalty"));

  return (
    <DraftContext.Provider value={draft}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </DraftContext.Provider>
  );
}

export function useDraft(): Draft {
  const draft = useContext(DraftContext);
  if (!draft) throw new Error("useDraft must be used inside a DraftProvider");
  return draft;
}

export function useDraftDispatch(): Dispatch<DraftAction> {
  const dispatch = useContext(DispatchContext);
  if (!dispatch) throw new Error("useDraftDispatch must be used inside a DraftProvider");
  return dispatch;
}
