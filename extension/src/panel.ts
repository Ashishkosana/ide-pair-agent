import * as vscode from "vscode";

import { ContextAccepted, ReplyPayload } from "./bridge";

export class ReplyView implements vscode.Disposable {
  private output: vscode.OutputChannel;
  private panel: vscode.WebviewPanel | undefined;

  constructor() {
    this.output = vscode.window.createOutputChannel("Pair Agent");
  }

  showAccepted(accepted: ContextAccepted): void {
    this.output.show(true);
    this.output.appendLine("—");
    this.output.appendLine(`context_id: ${accepted.context_id}`);
    this.output.appendLine(`accepted: ${accepted.accepted}`);
    this.output.appendLine(`policy: ${accepted.policy.mode} — ${accepted.policy.reason}`);
    this.output.appendLine(`channels: ${accepted.channels.join(", ") || "(none)"}`);
    if (accepted.redacted) {
      this.output.appendLine(
        `redacted: ${accepted.redaction_hits.join(", ") || "yes"}`
      );
    }
    if (accepted.mailbox_path) {
      this.output.appendLine(`mailbox: ${accepted.mailbox_path}`);
    }
  }

  showReply(reply: ReplyPayload): void {
    this.output.appendLine("");
    this.output.appendLine(`reply from ${reply.source}:`);
    this.output.appendLine(reply.text);
    this.renderWebview(reply.text, reply.source);
  }

  showWaiting(contextId: string): void {
    this.output.appendLine(`Waiting for POST /v1/assistant-reply (context ${contextId})…`);
  }

  showNoReply(contextId: string): void {
    const message =
      `No reply yet for ${contextId}. An assistant or script can POST ` +
      `/v1/assistant-reply; re-run a command or poll GET /v1/replies/latest.`;
    this.output.appendLine(message);
    vscode.window.showInformationMessage(
      "Pair Agent accepted context. No assistant reply arrived before the poll timeout."
    );
  }

  showError(error: unknown): void {
    const text = error instanceof Error ? error.message : String(error);
    this.output.appendLine(`error: ${text}`);
    vscode.window.showErrorMessage(`Pair Agent: ${text}`);
  }

  private renderWebview(text: string, source: string): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        "idePairAgentReply",
        "Pair Agent Reply",
        vscode.ViewColumn.Beside,
        { enableScripts: false }
      );
      this.panel.onDidDispose(() => {
        this.panel = undefined;
      });
    }
    const escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    const escapedSource = source
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    this.panel.webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';" />
  <title>Pair Agent Reply</title>
  <style>
    body { font-family: var(--vscode-font-family); padding: 1rem; }
    .meta { opacity: 0.7; margin-bottom: 1rem; }
    pre { white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="meta">Source: ${escapedSource}</div>
  <pre>${escaped}</pre>
</body>
</html>`;
    this.panel.reveal(vscode.ViewColumn.Beside, true);
  }

  dispose(): void {
    this.output.dispose();
    this.panel?.dispose();
  }
}
