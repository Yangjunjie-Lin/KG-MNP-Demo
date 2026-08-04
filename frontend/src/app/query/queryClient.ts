import { QueryClient } from "@tanstack/react-query";
import { isApiError } from "../../api/errors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, error) => {
        if (isApiError(error) && (!error.retryable || error.status === 404 || error.status === 422)) {
          return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});
