// SSE-Event-Schema fuer /<slug>/chats/{id}/messages.
// Quelle: lib/events.py + agents/manager/agent.py emit()-Aufrufe.

export type SseEventType =
  | "trace_started"
  | "intent_classified"
  | "mcp_connected"
  | "llm_request"
  | "llm_delta"
  | "llm_response"
  | "tool_call_started"
  | "tool_call_result"
  | "error"
  | "trace_completed";

export interface TraceEnvelope {
  trace_uid: string;
  tenant_id: string;
  chat_id: number;
  started_at: string;
}

export interface TraceEvent {
  trace_uid: string;
  sequence: number;
  timestamp: string;
  event_type: SseEventType;
  data: Record<string, unknown>;
}

export interface DoneEnvelope {
  trace_uid: string;
  status: "ok" | "error";
  response: string;
  intent: string;
  tool_calls: unknown[];
  duration_ms: number;
  error_message: string;
  chat_id: number;
}

// Spezielle Daten-Shapes pro Event-Type (best effort — Backend kann beliebige Felder mitschicken)
export interface IntentClassifiedData {
  intent?: string;
  model?: string;
  duration_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
}

export interface LlmRequestData {
  model?: string;
  messages_count?: number;
  has_tools?: boolean;
  round?: number;
}

export interface LlmDeltaData {
  round?: number;
  content_delta?: string;
}

export interface LlmResponseData {
  model?: string;
  duration_ms?: number;
  has_tool_calls?: boolean;
  content_preview?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
}

export interface ToolCallStartedData {
  tool_name?: string;
  call_id?: string;
  args?: Record<string, unknown>;
}

export interface ToolCallResultData {
  tool_name?: string;
  call_id?: string;
  duration_ms?: number;
  result_preview?: string;
  is_error?: boolean;
}

export interface ErrorData {
  error_type?: string;
  message?: string;
}

export interface TraceCompletedData {
  response?: string;
  total_duration_ms?: number;
  status?: string;
}
