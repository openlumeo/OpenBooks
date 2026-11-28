import type { Metadata } from "next";
import { pageMetadata, siteUrl } from "@/lib/site";
import { StructuredData } from "@/components/structured-data";
import { NavSentinel, LandingNav } from "@/components/landing/landing-nav";
import { Hero } from "@/components/landing/hero";
import { AgentStart } from "@/components/landing/agent-start";
import { ScrollStory } from "@/components/landing/scroll-story";
import { Refusals } from "@/components/landing/refusals";
import { Trace } from "@/components/landing/trace";
import { Inputs } from "@/components/landing/inputs";
import { AskDemo } from "@/components/landing/ask-demo";
import { FinalCta } from "@/components/landing/final-cta";

const description =
  "Open Books releases a financial file only when its own arithmetic proves it. Anything else comes back as a typed refusal that says why.";

export const metadata: Metadata = pageMetadata({
  title: "Bank statement to verified JSON | Open Books",
  description,
  path: "/",
});

export default function LandingPage() {
  return (
    <div className="lp-page">
      <div className="lp-atmosphere" aria-hidden="true" />
      <NavSentinel />
      <LandingNav />
      <main id="content">
        <Hero />
        <AgentStart />
        <ScrollStory />
        <Inputs />
        <Refusals />
        <Trace />
        <AskDemo />
        <FinalCta />
      </main>
      <StructuredData
        data={{
          "@context": "https://schema.org",
          "@type": "Organization",
          name: "Lumeo",
          url: siteUrl.href,
          sameAs: ["https://github.com/Sagexd08/OpenBooks", "https://www.npmjs.com/package/@lumeo_hq/openbooks"],
        }}
      />
      <StructuredData
        data={{
          "@context": "https://schema.org",
          "@type": "WebSite",
          name: "Open Books by Lumeo",
          alternateName: "Open Books",
          url: siteUrl.href,
        }}
      />
      <StructuredData
        data={{
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          name: "Open Books by Lumeo",
          alternateName: "Open Books",
          url: siteUrl.href,
          description,
          applicationCategory: "FinanceApplication",
          operatingSystem: "Web",
        }}
      />
    </div>
  );
}
