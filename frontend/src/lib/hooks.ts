import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Category,
  type Source,
  type Stats,
  type SystemSettings,
  type TaskRun,
} from "./api";
export const useSources = () =>
  useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/sources"),
    refetchInterval: 5000,
  });
export const useCategories = () =>
  useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/categories"),
  });
export const useSettings = () =>
  useQuery({
    queryKey: ["settings"],
    queryFn: () => api<SystemSettings>("/settings"),
  });
export const useStats = () =>
  useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("/stats"),
    refetchInterval: 5000,
  });
export const useTasks = () =>
  useQuery({
    queryKey: ["tasks"],
    queryFn: () => api<TaskRun[]>("/tasks"),
    refetchInterval: 3000,
  });
export function useAction<T = unknown>(method = "POST") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) =>
      api<T>(path, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
    onSuccess: () => client.invalidateQueries(),
  });
}
