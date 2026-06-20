import { apiFetch, tenantUrl } from "./client";
import type { EntityCls, EntityDetailResponse } from "./types";

export function fetchEntity(
  slug: string,
  cls: EntityCls,
  id: number,
): Promise<EntityDetailResponse> {
  return apiFetch(tenantUrl(slug, `/entity/${cls}/${id}`));
}
