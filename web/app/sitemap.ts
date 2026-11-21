import type { MetadataRoute } from "next";
import { docs } from "@/lib/docs";
import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return docs.getPages().map((page) => ({
    url: new URL(page.url, siteUrl).href,
  }));
}
