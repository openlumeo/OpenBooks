import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Open Books by Lumeo",
    short_name: "Open Books",
    description: "Financial documents in, one proven JSON per file out, or a typed refusal.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b0f08",
    theme_color: "#0b0f08",
    icons: [{ src: "/favicon.ico", sizes: "any", type: "image/x-icon" }],
  };
}
