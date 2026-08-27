import { createContext, useContext, useMemo, useState, type PropsWithChildren } from "react";
import type { components } from "../../api/schema";
import { ProvenanceDrawer } from "./ProvenanceDrawer";
import { SourcePreviewDrawer, type SourceReferenceWithUpload } from "./SourcePreviewDrawer";

type Provenance = components["schemas"]["MetricProvenance"];
type ContextValue = { open: (metric: Provenance) => void; openSourcePreview: (reference: SourceReferenceWithUpload) => void };
const Context = createContext<ContextValue | null>(null);

export function ProvenanceProvider({ children }: PropsWithChildren) {
  const [metric, setMetric] = useState<Provenance | null>(null);
  // Separate from `metric`: a table row's own "Источник" cell opens the
  // exact-cell preview directly (one click, matching every other preview
  // entry point in this app) rather than first showing a reference list
  // that only ever has the one entry.
  const [sourcePreview, setSourcePreview] = useState<SourceReferenceWithUpload | null>(null);
  const value = useMemo(() => ({ open: setMetric, openSourcePreview: setSourcePreview }), []);
  return (
    <Context.Provider value={value}>
      {children}
      <ProvenanceDrawer metric={metric} onClose={() => setMetric(null)} />
      <SourcePreviewDrawer reference={sourcePreview} onClose={() => setSourcePreview(null)} />
    </Context.Provider>
  );
}

export function useProvenance(): ContextValue {
  const context = useContext(Context);
  return context ?? { open: () => undefined, openSourcePreview: () => undefined };
}
