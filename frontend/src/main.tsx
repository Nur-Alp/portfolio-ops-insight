import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthGate } from "./auth/AuthGate";
import { LanguageProvider } from "./i18n";
import { ProvenanceProvider } from "./components/ui/ProvenanceContext";
import { router } from "./router";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LanguageProvider>
      <QueryClientProvider client={queryClient}>
        <ProvenanceProvider>
          <AuthGate>
            <RouterProvider router={router} />
          </AuthGate>
        </ProvenanceProvider>
      </QueryClientProvider>
    </LanguageProvider>
  </StrictMode>
);
