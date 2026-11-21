import type { ReactNode } from "react";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import { RootProvider } from "fumadocs-ui/provider/next";
import { BookOpen, PanelTop } from "lucide-react";
import { docs } from "@/lib/docs";
import { repositoryUrl } from "@/lib/site";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="ob-docs">
      <RootProvider theme={{ defaultTheme: "dark", storageKey: "openbooks-docs-theme" }}>
        <DocsLayout
          tree={docs.getPageTree()}
          nav={{
            url: "/docs",
            title: <span className="flex items-center gap-2 font-semibold"><BookOpen size={19} aria-hidden="true" /> Open Books for developers</span>,
          }}
          links={[{ text: "Workspace", url: "/", icon: <PanelTop size={16} aria-hidden="true" /> }]}
          githubUrl={repositoryUrl}
        >
          {children}
        </DocsLayout>
      </RootProvider>
    </div>
  );
}
