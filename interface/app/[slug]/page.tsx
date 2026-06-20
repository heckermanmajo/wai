import { ChatShell } from "@/components/chat/ChatShell";

export default async function ChatPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <ChatShell slug={slug} />;
}
