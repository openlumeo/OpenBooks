import { loader } from "fumadocs-core/source";
import { defineDocs } from "fumadocs-mdx/macro";

const content = defineDocs({ dir: "content/docs" });

export const docs = loader({
  baseUrl: "/docs",
  source: content.toFumadocsSource(),
});
