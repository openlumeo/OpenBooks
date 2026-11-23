import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = {
  ...pageMetadata({
    title: "Sign in",
    description: "Sign in to your Open Books account to use the browser workspace for bank statements, settlements and tax documents and their JSON output.",
    path: "/auth/sign-in",
  }),
  robots: { index: false, follow: true },
};

export default function SignInPage() {
  return <AuthForm mode="sign-in" />;
}
