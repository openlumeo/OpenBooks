import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = {
  ...pageMetadata({
    title: "Create account",
    description: "Create an Open Books account to use the browser workspace for bank statements, settlements and tax documents and their JSON output.",
    path: "/auth/sign-up",
  }),
  robots: { index: false, follow: true },
};

export default function SignUpPage() {
  return <AuthForm mode="sign-up" />;
}
