import { notFound } from "next/navigation";
import { DocsBody, DocsDescription, DocsPage, DocsTitle } from "fumadocs-ui/layouts/docs/page";
import { docs } from "@/lib/docs";
import { markdownPath } from "@/lib/docs-markdown";
import { pageMetadata, siteUrl } from "@/lib/site";
import { StructuredData } from "@/components/structured-data";
import { docsComponents } from "./mdx";
import { DocsBanner } from "./docs-banner";

export function docMetadata(slug: string[]) {
  const page = docs.getPage(slug);
  if (!page) notFound();

  const metadata = pageMetadata({
    title: page.data.title,
    description: page.data.description ?? "",
    path: page.url,
  });
  return {
    ...metadata,
    alternates: {
      ...metadata.alternates,
      types: { "text/markdown": [{ url: markdownPath(page), title: page.data.title }] },
    },
  };
}

export function DocArticle({ slug }: { slug: string[] }) {
  const page = docs.getPage(slug);
  if (!page) notFound();

  const Body = page.data.body;
  return (
    <DocsPage toc={page.data.toc}>
      {page.url === "/docs" ? <StructuredData data={{
        "@context": "https://schema.org",
        "@type": "WebSite",
        name: "Open Books by Lumeo",
        alternateName: "Open Books",
        url: siteUrl.href,
      }} /> : <StructuredData data={{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Developer docs", item: siteUrl.href },
          { "@type": "ListItem", position: 2, name: page.data.title, item: new URL(page.url, siteUrl).href },
        ],
      }} />}
      {page.url === "/docs" && <DocsBanner />}
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody><Body components={docsComponents} /></DocsBody>
      <a href={markdownPath(page)} className="mb-3 text-sm text-fd-muted-foreground underline underline-offset-4">View this page as Markdown</a>
    </DocsPage>
  );
}
