export function byId<T extends { id: string }>(rows: T[], id: string | null | undefined) {
  return id ? rows.find((row) => row.id === id) : undefined;
}
