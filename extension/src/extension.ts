import * as vscode from "vscode";

import { BridgeClient } from "./bridge";
import { collectContext } from "./collect";
import { ReplyView } from "./panel";
import { Intent } from "./protocol";

function settings() {
  const config = vscode.workspace.getConfiguration("idePairAgent");
  return {
    bridgeUrl: config.get<string>("bridgeUrl", "http://127.0.0.1:8765").replace(/\/$/, ""),
    pollMs: config.get<number>("pollMs", 1000),
    pollTimeoutMs: config.get<number>("pollTimeoutMs", 30000),
    maxFileChars: config.get<number>("maxFileChars", 100000),
  };
}

async function runIntent(intent: Intent, view: ReplyView): Promise<void> {
  const opts = settings();
  if (!opts.bridgeUrl.startsWith("http://127.0.0.1") && !opts.bridgeUrl.startsWith("http://localhost")) {
    throw new Error(
      "M1 only posts to a loopback bridge. Set idePairAgent.bridgeUrl to http://127.0.0.1:<port>."
    );
  }

  let prompt: string | null = null;
  if (intent === "ask") {
    prompt =
      (await vscode.window.showInputBox({
        prompt: "What should the pair agent ask the assistant?",
        placeHolder: "Why is this diagnostic firing?",
      })) ?? null;
    if (prompt === null) {
      return;
    }
  }

  const payload = await collectContext(intent, prompt, opts.maxFileChars);
  const bridge = new BridgeClient(opts.bridgeUrl);
  await bridge.health();
  const accepted = await bridge.postContext(payload);
  view.showAccepted(accepted);

  if (!accepted.accepted) {
    vscode.window.showWarningMessage("Pair Agent policy dropped this context.");
    return;
  }

  vscode.window.setStatusBarMessage(
    `Pair Agent sent ${intent} (${accepted.context_id.slice(0, 8)}…)`,
    5000
  );
  view.showWaiting(accepted.context_id);
  const reply = await bridge.waitForReply(
    accepted.context_id,
    opts.pollMs,
    opts.pollTimeoutMs
  );
  if (reply) {
    view.showReply(reply);
  } else {
    view.showNoReply(accepted.context_id);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const view = new ReplyView();
  const wrap = (intent: Intent) => async () => {
    try {
      await runIntent(intent, view);
    } catch (error) {
      view.showError(error);
    }
  };

  context.subscriptions.push(
    view,
    vscode.commands.registerCommand("idePairAgent.shareSelection", wrap("share_selection")),
    vscode.commands.registerCommand(
      "idePairAgent.shareFileDiagnostics",
      wrap("share_file_diagnostics")
    ),
    vscode.commands.registerCommand("idePairAgent.ask", wrap("ask"))
  );
}

export function deactivate(): void {
  // nothing to tear down beyond subscriptions
}
