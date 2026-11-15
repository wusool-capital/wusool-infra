export function byId<T extends { id: string }>(rows: T[], id: string | undefined) {
  return id ? rows.find((row) => row.id === id) : undefined;
}
