import type { ReactNode } from "react";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import { RootProvider } from "fumadocs-ui/provider/next";
import { FileText, PanelTop } from "lucide-react";
import { docs } from "@/lib/docs";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { THEME_STORAGE_KEY } from "@/components/brand/theme-script";
import { SiteFooter } from "@/components/landing/site-footer";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="ob-docs">
      <RootProvider theme={{ attribute: ["class", "data-theme"], defaultTheme: "dark", enableSystem: false, storageKey: THEME_STORAGE_KEY }}>
        <DocsLayout
          tree={docs.getPageTree()}
          nav={{
            url: "/docs",
            title: (
              <span className="flex items-center gap-3">
                <BrandLockup markSize={22} />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: ".12em", textTransform: "uppercase", color: "var(--text-faint)" }}>Docs</span>
              </span>
            ),
          }}
          links={[
            { text: "Open workspace", url: "/app", icon: <PanelTop size={16} aria-hidden="true" /> },
            { text: "Docs for AI agents", url: "/llms.txt", icon: <FileText size={16} aria-hidden="true" /> },
          ]}
        >
          {children}
        </DocsLayout>
      </RootProvider>
      <SiteFooter />
    </div>
  );
}
