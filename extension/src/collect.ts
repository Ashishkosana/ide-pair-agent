import { execFile } from "node:child_process";
import { promisify } from "node:util";
import * as path from "node:path";
import * as vscode from "vscode";

import {
  DiagnosticPayload,
  FilePayload,
  IdeContextPayload,
  Intent,
  SCHEMA_VERSION,
  Severity,
  CLIENT,
  capText,
} from "./protocol";

const execFileAsync = promisify(execFile);

export async function detectGitBranch(cwd: string): Promise<string | undefined> {
  try {
    const { stdout } = await execFileAsync(
      "git",
      ["rev-parse", "--abbrev-ref", "HEAD"],
      { cwd, timeout: 2000 }
    );
    const branch = stdout.trim();
    if (!branch || branch === "HEAD") {
      return undefined;
    }
    return branch;
  } catch {
    return undefined;
  }
}

function mapSeverity(severity: vscode.DiagnosticSeverity): Severity {
  switch (severity) {
    case vscode.DiagnosticSeverity.Error:
      return "error";
    case vscode.DiagnosticSeverity.Warning:
      return "warning";
    case vscode.DiagnosticSeverity.Information:
      return "info";
    default:
      return "hint";
  }
}

export function collectDiagnostics(document: vscode.TextDocument): DiagnosticPayload[] {
  return vscode.languages.getDiagnostics(document.uri).map((diagnostic) => ({
    severity: mapSeverity(diagnostic.severity),
    message: diagnostic.message,
    source: diagnostic.source ?? null,
    start_line: diagnostic.range.start.line + 1,
    end_line: diagnostic.range.end.line + 1,
  }));
}

export async function collectContext(
  intent: Intent,
  prompt: string | null,
  maxFileChars: number
): Promise<IdeContextPayload> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    throw new Error("No active editor. Open a file first.");
  }

  const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
  const workspacePath = folder?.uri.fsPath ?? vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const relativePath = workspacePath
    ? path.relative(workspacePath, editor.document.uri.fsPath)
    : editor.document.uri.fsPath;

  const gitBranch = workspacePath ? await detectGitBranch(workspacePath) : undefined;
  const selection = editor.selection;
  const selectionText = editor.document.getText(selection);
  const includeFile = intent === "share_file_diagnostics";
  const includeSelection =
    intent === "share_selection" || intent === "ask" || !selection.isEmpty;

  if (intent === "share_selection" && selection.isEmpty) {
    throw new Error("No selection. Highlight code, then run Share Selection again.");
  }

  const file: FilePayload = {
    path: relativePath || null,
    language_id: editor.document.languageId,
    content: includeFile ? capText(editor.document.getText(), maxFileChars).text : null,
    selection:
      includeSelection && selectionText
        ? {
            text: capText(selectionText, maxFileChars).text,
            start_line: selection.start.line + 1,
            end_line: selection.end.line + 1,
          }
        : null,
  };

  return {
    schema_version: SCHEMA_VERSION,
    intent,
    prompt,
    workspace: {
      folder: workspacePath ?? null,
      git_branch: gitBranch ?? null,
    },
    file,
    diagnostics: collectDiagnostics(editor.document),
    client: CLIENT,
  };
}
