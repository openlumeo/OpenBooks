import { loader } from "fumadocs-core/source";
import { defineDocs } from "fumadocs-mdx/macro";

const content = defineDocs({
  dir: "content/docs",
  docs: { postprocess: { includeProcessedMarkdown: true } },
});

export const docs = loader({
  baseUrl: "/docs",
  url: (slugs) => slugs.length === 0 ? "/" : "/docs/" + slugs.join("/"),
  source: content.toFumadocsSource(),
});
