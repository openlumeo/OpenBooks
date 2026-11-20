import type { Metadata } from "next";
import { Landing } from "@/components/landing/landing";

export const metadata: Metadata = {
  title: "Open Books: statements in, one proven JSON out",
  description:
    "Open Books reads bank statements, gateway settlements and tax documents, proves the balance, and releases one JSON per file, or a typed refusal.",
  robots: { index: true, follow: true },
};

export default function Page() {
  return <Landing />;
}
