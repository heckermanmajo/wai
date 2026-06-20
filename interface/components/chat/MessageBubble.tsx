"use client";

import type { MessageDto } from "@/lib/api/types";
import { MarkdownView } from "@/components/markdown/MarkdownView";
import styles from "./MessageBubble.module.css";

export function MessageBubble({ msg }: { msg: MessageDto }) {
  const role = msg.role;
  const isUser = role === "user";
  const isTool = role === "tool";

  return (
    <div className={styles.msg} data-role={role}>
      <div className={styles.role}>{isUser ? "Du" : isTool ? `tool · ${msg.tool_name ?? ""}` : "wai"}</div>
      {isUser || isTool ? (
        <div className={styles.body}>{msg.content}</div>
      ) : (
        <MarkdownView content={msg.content} className={styles.body} />
      )}
      {msg.tool_calls.length > 0 && (
        <div className={styles.toolCalls}>
          {msg.tool_calls.map((tc) => (
            <details key={tc.tool_call_id} className={styles.toolCall}>
              <summary>
                <code>{tc.tool_name}</code>
                <span className={styles.toolStatus} data-status={tc.status}>{tc.status}</span>
                {tc.duration_ms > 0 && <span className={styles.toolMs}>{tc.duration_ms}ms</span>}
              </summary>
              <pre className={styles.toolArgs}>{tc.arguments_json}</pre>
              {tc.result_text && <pre className={styles.toolResult}>{tc.result_text}</pre>}
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
