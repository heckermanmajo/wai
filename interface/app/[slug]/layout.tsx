import { redirect } from "next/navigation";
import { requireMe } from "@/lib/server/me";
import { MeProvider } from "@/components/providers/MeProvider";

export default async function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const me = await requireMe();
  if (me.tenant_slug !== slug) {
    // Cookie passt zu anderem Tenant — sauberster Weg ist Re-Login
    redirect(`/${me.tenant_slug}`);
  }
  return <MeProvider me={me}>{children}</MeProvider>;
}
