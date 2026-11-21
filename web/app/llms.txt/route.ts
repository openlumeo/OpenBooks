import { docs } from "@/lib/docs";
import { docsText, markdownPath } from "@/lib/docs-markdown";
import { siteUrl } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const index = docs.getPages();
  const lines = index.map((page) => {
    const url = new URL(markdownPath(page), siteUrl).href;
    return "- [" + page.data.title + "](" + url + "): " + (page.data.description ?? "");
  });
  return docsText([
    "# Open Books by Lumeo",
    "",
    "> Open Books turns bank statements, payment settlements, tax documents and workpapers into verified JSON or a typed refusal. These are the public developer docs and package reference.",
    "",
    "## Documentation",
    "",
    ...lines,
    "",
    "## Optional",
    "",
    "- [Complete documentation as text](" + new URL("/llms-full.txt", siteUrl).href + ")",
    "",
  ].join("\n"));
}
