
import { QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./app/App.tsx";
import { queryClient } from "./app/query/queryClient";
import "./styles/index.css";

async function bootstrap() {
  if (import.meta.env.VITE_DATA_SOURCE === "mock") {
    const { worker } = await import("./mocks/browser");
    await worker.start({ onUnhandledRequest: "bypass" });
  }
  createRoot(document.getElementById("root")!).render(
    <QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider>,
  );
}

void bootstrap();
