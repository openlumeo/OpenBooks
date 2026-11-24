import { Workspace } from "@/components/workspace/workspace";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workspace",
  robots: { index: false, follow: true },
};

export default function Page() {
  return (
    <>
      <a href="#conversation" className="skip-link">
        Skip to conversation
      </a>
      <Workspace />
    </>
  );
}
