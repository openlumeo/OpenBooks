import { docs } from "@/lib/docs";
import { docsText, renderDocMarkdown } from "@/lib/docs-markdown";

export const dynamic = "force-static";

export async function GET() {
  const pages = await Promise.all(docs.getPages().map(renderDocMarkdown));
  return docsText(pages.join("\n---\n\n"));
}
