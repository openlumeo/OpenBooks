import type { Metadata } from "next";

export const siteUrl = new URL("https://openbooks.lumeo.co.in");
export const repositoryUrl = "https://github.com/Sagexd08/OpenBooks";

export function pageMetadata({
  title, description, path,
}: { title: string; description: string; path: string }): Metadata {
  const socialTitle = title + " | Open Books";
  const images = [{
    url: "/opengraph-image",
    width: 1200,
    height: 630,
    alt: "Open Books by Lumeo developer documentation and workspace",
  }];
  return {
    title: path === "/" ? socialTitle : title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      title: socialTitle,
      description,
      siteName: "Open Books by Lumeo",
      url: path,
      images,
    },
    twitter: { card: "summary_large_image", title: socialTitle, description, images },
  };
}
