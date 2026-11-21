import { DocArticle, docMetadata } from "@/components/docs/article";

export const generateMetadata = () => docMetadata([]);

export default function Page() {
  return <DocArticle slug={[]} />;
}
