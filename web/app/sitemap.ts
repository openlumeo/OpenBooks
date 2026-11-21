import type { MetadataRoute } from "next";
import { docs } from "@/lib/docs";
import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", ...docs.getPages().map((page) => page.url)].map((path) => ({
    url: new URL(path, siteUrl).href,
  }));
}
