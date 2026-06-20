// DTOs spiegeln die FastAPI-JSON-Antworten 1:1.
// Quelle der Wahrheit: gateway/main.py — bei Aenderungen synchronisieren.

export interface MeResponse {
  user_id: number;
  username: string;
  display_name: string;
  tenant_slug: string;
  tenant_id: number;
  tenant_role: string;
}

export interface DevUser {
  username: string;
  email: string;
  display_name: string;
  tenants: string[];
}

export interface LoginOk {
  status: "ok";
  tenant_slug: string;
  tenant_name?: string;
  user: { user_id: number; username: string; display_name: string };
}

export interface LoginPick {
  status: "pick";
  pending_token: string;
  tenants: { slug: string; name: string }[];
  user: { user_id: number; username: string; display_name: string };
}

export type LoginResponse = LoginOk | LoginPick;

export interface ChatListItem {
  id: number;
  title: string;
  agent_name: string;
  model: string;
  is_shared: boolean;
  is_mine: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ToolCallDto {
  tool_call_id: string;
  tool_name: string;
  arguments_json: string;
  result_text: string;
  status: string;
  duration_ms: number;
}

export interface MessageDto {
  id: number;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_call_id: string | null;
  tool_name: string | null;
  tool_calls: ToolCallDto[];
  created_at: string | null;
}

export interface ChatDetail {
  id: number;
  title: string;
  user_id: number;
  is_shared: boolean;
  is_mine: boolean;
  messages: MessageDto[];
}

export interface ArtifactFile {
  id: number;
  filename: string;
  mime: string;
  size_bytes: number;
  source: string;
  minio_key: string;
  relation: string;
  created_at: string | null;
}

export interface ArtifactDocument {
  id: number;
  title: string;
  version: number;
  author_display_name: string;
  relation: string;
  updated_at: string | null;
}

export interface ArtifactCrmEntity {
  artifact_cls: string;
  artifact_id: number;
  relation: string;
  created_at: string | null;
}

export interface ArtifactToolCall {
  id: number;
  tool_name: string;
  arguments_json: string;
  result_text: string;
  status: string;
  duration_ms: number;
  created_at: string | null;
}

export interface ChatArtifacts {
  files: ArtifactFile[];
  documents: ArtifactDocument[];
  crm_entities: ArtifactCrmEntity[];
  tasks_notes_comments: {
    tasks: { id: number; title: string; status: string }[];
    notes: { id: number; title: string; body: string }[];
    comments: { id: number; body: string }[];
  };
  tool_calls: ArtifactToolCall[];
}

export interface DocumentListItem {
  id: number;
  title: string;
  author_user_id: number;
  author_display_name: string;
  target_cls: string;
  target_id: number;
  version: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentDetail extends DocumentListItem {
  content: string;
  format: string;
}

export interface DocumentVersionListItem {
  id: number;
  version: number;
  title: string;
  author_user_id: number;
  author_display_name: string;
  content_hash: string;
  content_length: number;
  created_at: string | null;
}

export interface DocumentVersionDetail extends DocumentVersionListItem {
  document_id: number;
  format: string;
  content: string;
  change_summary: string;
  updated_at: string | null;
}

export interface DiffSegment {
  kind: "equal" | "replace" | "delete" | "insert";
  old_start: number;
  old_end: number;
  new_start: number;
  new_end: number;
  old_text: string;
  new_text: string;
}

export interface DocumentDiff {
  from: { id: number; version: number; title: string; label: string };
  to: { id: number; version: number; title: string; label: string };
  title_diff: { kind: string; from: string; to: string }[];
  content_diff: DiffSegment[];
  unified: string;
}

export interface EntityDetailResponse {
  cls: string;
  id: number;
  data: Record<string, unknown>;
}

export type EntityCls = "contact" | "account" | "lead" | "deal";

export interface ActionDto {
  key: string;
  label: string;
  description: string;
  icon: string;
  category: string;
  resource_types: string[];
  execution_kind: string;
  needs_confirmation: boolean;
  is_destructive: boolean;
  refine_score: number;
  refine_reason: string;
}

export interface ActionsResponse {
  resource: { cls: string; id: number; name?: string; short?: string } | null;
  actions: ActionDto[];
}

export interface ActionChatTaskResult {
  kind: "chat_task";
  chat_id: number;
  prompt: string;
  action: ActionDto;
}

export interface ActionToolCallResult {
  kind: "tool_call";
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  action: ActionDto;
}

export type ActionRunResult = ActionChatTaskResult | ActionToolCallResult;

export interface TraceRow {
  trace_uid: string;
  status: string;
  tenant_id: string;
  intent: string;
  user_message: string;
  response: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number;
  event_count: number;
  tool_call_count: number;
  error_message: string;
}

export interface TraceListResponse {
  traces: TraceRow[];
  limit: number;
  offset: number;
  count: number;
}

export interface TraceEventDto {
  trace_uid: string;
  sequence: number;
  timestamp: string;
  event_type: string;
  data: Record<string, unknown>;
}

export interface TraceDetailResponse {
  trace: TraceRow;
  events: TraceEventDto[];
}

export interface IngestVoiceResponse {
  attachment_id: number;
  minio_key: string;
  transcript: string;
  model?: string;
  duration_seconds?: number;
  transcribe_error?: string;
}

export interface IngestImageResponse {
  attachment_id: number;
  minio_key: string;
  mime: string;
  size_bytes: number;
  presigned_url: string;
}
