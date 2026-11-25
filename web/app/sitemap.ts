import type { MetadataRoute } from "next";
import { docs } from "@/lib/docs";
import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: new URL("/", siteUrl).href },
    { url: new URL("/get-started", siteUrl).href },
    { url: new URL("/benchmark", siteUrl).href },
    ...docs.getPages().map((page) => ({
      url: new URL(page.url, siteUrl).href,
    })),
  ];
}
