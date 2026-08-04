import "@testing-library/jest-dom/vitest";
import { transferableAbortController } from "node:util";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "../mocks/server";

// jsdom's AbortSignal belongs to a different realm than Node's fetch/MSW.
const nativeController = transferableAbortController();
globalThis.AbortController = nativeController.constructor as typeof AbortController;
globalThis.AbortSignal = nativeController.signal.constructor as typeof AbortSignal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
