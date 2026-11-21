import { notFound } from "next/navigation";
import { DocsBody, DocsDescription, DocsPage, DocsTitle, EditOnGitHub } from "fumadocs-ui/layouts/docs/page";
import { docs } from "@/lib/docs";
import { pageMetadata, repositoryUrl, siteUrl } from "@/lib/site";
import { StructuredData } from "@/components/structured-data";
import { docsComponents } from "@/components/docs/mdx";

type Props = { params: Promise<{ slug?: string[] }> };

export const dynamicParams = false;
export const generateStaticParams = () => docs.generateParams();

export async function generateMetadata({ params }: Props) {
  const page = docs.getPage((await params).slug);
  if (!page) notFound();

  return pageMetadata({
    title: page.data.title,
    description: page.data.description ?? "",
    path: page.url,
  });
}

export default async function Page({ params }: Props) {
  const page = docs.getPage((await params).slug);
  if (!page) notFound();

  const Body = page.data.body;
  return (
    <DocsPage toc={page.data.toc}>
      {page.url !== "/docs" && <StructuredData data={{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Developer docs", item: new URL("/docs", siteUrl).href },
          { "@type": "ListItem", position: 2, name: page.data.title, item: new URL(page.url, siteUrl).href },
        ],
      }} />}
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody><Body components={docsComponents} /></DocsBody>
      <EditOnGitHub href={repositoryUrl + "/edit/main/web/content/docs/" + page.path}>Edit this page on GitHub</EditOnGitHub>
    </DocsPage>
  );
}
