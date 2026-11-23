import type { Metadata } from "next";

export const siteUrl = new URL("https://openbooks.lumeo.co.in");

export function pageMetadata({
  title, description, path,
}: { title: string; description: string; path: string }): Metadata {
  const socialTitle = path === "/" ? title : title + " | Open Books";
  const images = [{
    url: "/og.png",
    width: 1920,
    height: 1080,
    alt: "Open Books by Lumeo: financial documents to proven JSON",
  }];
  return {
    title: path === "/" ? { absolute: title } : title,
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
