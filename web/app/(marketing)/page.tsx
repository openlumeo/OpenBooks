import type { Metadata } from "next";
import { pageMetadata, siteUrl } from "@/lib/site";
import { StructuredData } from "@/components/structured-data";
import { NavSentinel, LandingNav } from "@/components/landing/landing-nav";
import { Hero } from "@/components/landing/hero";
import { Reframe } from "@/components/landing/reframe";
import { ScrollStory } from "@/components/landing/scroll-story";
import { Refusals } from "@/components/landing/refusals";
import { Trace } from "@/components/landing/trace";
import { Inputs } from "@/components/landing/inputs";
import { TryIt } from "@/components/landing/try-it";
import { AskDemo } from "@/components/landing/ask-demo";
import { FinalCta } from "@/components/landing/final-cta";
import { SiteFooter } from "@/components/landing/site-footer";

const description =
  "Open Books releases a financial file only when its own arithmetic proves it. Anything else comes back as a typed refusal that says why.";

export const metadata: Metadata = pageMetadata({
  title: "Open Books by Lumeo",
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
        <Reframe />
        <ScrollStory />
        <Refusals />
        <Trace />
        <Inputs />
        <TryIt />
        <AskDemo />
        <FinalCta />
      </main>
      <SiteFooter />
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
