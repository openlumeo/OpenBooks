// The original File objects for this tab only. History keeps results, never file bytes, so a re-run
// works until the page reloads; after that the card asks the user to attach the file again.
const files = new Map<string, File[]>();

export function rememberFiles(turnId: string, list: File[]) {
  files.set(turnId, list);
}

export function recallFile(turnId: string, index: number): File | undefined {
  return files.get(turnId)?.[index];
}
