import { createFromSource } from "fumadocs-core/search/server";
import { docs } from "@/lib/docs";

export const { GET } = createFromSource(docs, { language: "english" });
