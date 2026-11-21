import { Workspace } from "@/components/workspace";
import { pageMetadata, siteUrl } from "@/lib/site";
import { StructuredData } from "@/components/structured-data";

export const metadata = pageMetadata({
  title: "Financial Document Extraction Workspace",
  description:
    "Check bank statements, payment settlements, tax documents and Excel workpapers. Review evidence and download verified financial data as JSON.",
  path: "/",
});

export default function Page() {
  return (
    <>
      <StructuredData data={{
        "@context": "https://schema.org",
        "@type": "WebSite",
        name: "Open Books by Lumeo",
        alternateName: "Open Books",
        url: siteUrl.href,
      }} />
      <a href="#conversation" className="skip-link">Skip to conversation</a>
      <Workspace />
    </>
  );
}
