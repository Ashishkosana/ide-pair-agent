import { IdeContextPayload } from "./protocol";

export interface ContextAccepted {
  context_id: string;
  accepted: boolean;
  redacted: boolean;
  redaction_hits: string[];
  truncated: boolean;
  channels: string[];
  policy: {
    mode: string;
    reason: string;
    forward: boolean;
    summarize: boolean;
    channels: string[];
  };
  webhook: Record<string, unknown>;
  mailbox_path: string | null;
  reply: ReplyPayload | null;
}

export interface ReplyPayload {
  reply_id: string;
  context_id: string | null;
  text: string;
  source: string;
  created_at: string;
}

export class BridgeClient {
  constructor(private readonly baseUrl: string) {}

  async health(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/v1/health`);
    if (!response.ok) {
      throw new Error(`Bridge health check failed (${response.status})`);
    }
  }

  async postContext(payload: IdeContextPayload): Promise<ContextAccepted> {
    const response = await fetch(`${this.baseUrl}/v1/context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Bridge rejected context (${response.status}): ${detail}`);
    }
    return (await response.json()) as ContextAccepted;
  }

  async latestReply(contextId: string): Promise<ReplyPayload | null> {
    const url = new URL(`${this.baseUrl}/v1/replies/latest`);
    url.searchParams.set("context_id", contextId);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Bridge reply poll failed (${response.status})`);
    }
    const body = (await response.json()) as { reply: ReplyPayload | null };
    return body.reply;
  }

  async waitForReply(
    contextId: string,
    pollMs: number,
    timeoutMs: number
  ): Promise<ReplyPayload | null> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const reply = await this.latestReply(contextId);
      if (reply) {
        return reply;
      }
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
    return null;
  }
}
