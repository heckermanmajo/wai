"use client";

import { EntityOverlay } from "./EntityOverlay";
import { DocumentOverlay } from "./DocumentOverlay";
import { DiffOverlay } from "./DiffOverlay";
import { ErrorOverlay } from "./ErrorOverlay";
import { ToastContainer } from "./ToastContainer";

export function Overlays({ slug }: { slug: string }) {
  return (
    <>
      <EntityOverlay slug={slug} />
      <DocumentOverlay slug={slug} />
      <DiffOverlay slug={slug} />
      <ErrorOverlay />
      <ToastContainer />
    </>
  );
}
