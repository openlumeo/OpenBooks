import { DocArticle, docMetadata } from "@/components/docs/article";
import { pageMetadata } from "@/lib/site";

export const generateMetadata = () => {
  const { alternates, ...metadata } = pageMetadata({
    title: "Developer docs for bank statement parsing",
    description: "Turn bank statements, settlements and tax files into verified JSON. Start with a sample, then integrate via CLI, Python, Node.js, HTTP or MCP.",
    path: "/docs",
  });
  return { ...metadata, alternates: { ...alternates, types: docMetadata([]).alternates.types } };
};

export default function Page() {
  return <DocArticle slug={[]} />;
}
