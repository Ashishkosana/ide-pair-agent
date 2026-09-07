/** Shared wire types for POST /v1/context. Keep in sync with the Python models. */

export const SCHEMA_VERSION = "1";

export const INTENTS = [
  "share_selection",
  "share_file_diagnostics",
  "ask",
] as const;

export type Intent = (typeof INTENTS)[number];

export type Severity = "error" | "warning" | "info" | "hint";

export interface SelectionPayload {
  text: string;
  start_line: number | null;
  end_line: number | null;
}

export interface FilePayload {
  path: string | null;
  language_id: string | null;
  content: string | null;
  selection: SelectionPayload | null;
}

export interface WorkspacePayload {
  folder: string | null;
  git_branch: string | null;
}

export interface DiagnosticPayload {
  severity: Severity;
  message: string;
  source: string | null;
  start_line: number | null;
  end_line: number | null;
}

export interface ClientPayload {
  name: string;
  version: string;
}

export interface IdeContextPayload {
  schema_version: string;
  intent: Intent;
  prompt: string | null;
  workspace: WorkspacePayload;
  file: FilePayload;
  diagnostics: DiagnosticPayload[];
  client: ClientPayload;
}

export const CLIENT: ClientPayload = {
  name: "ide-pair-agent-extension",
  version: "0.1.0",
};

export function capText(text: string, maxChars: number): { text: string; truncated: boolean } {
  if (text.length <= maxChars) {
    return { text, truncated: false };
  }
  return { text: `${text.slice(0, maxChars)}\n…[truncated]`, truncated: true };
}
