import { docs } from "@/lib/docs";
import { DocArticle, docMetadata } from "@/components/docs/article";

type Props = { params: Promise<{ slug: string[] }> };

export const dynamicParams = false;
export const generateStaticParams = () => docs.generateParams().filter(({ slug }) => slug.length > 0);

export async function generateMetadata({ params }: Props) {
  return docMetadata((await params).slug);
}

export default async function Page({ params }: Props) {
  return <DocArticle slug={(await params).slug} />;
}
