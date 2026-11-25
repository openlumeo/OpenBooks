import type { Metadata } from "next";
import Link from "next/link";
import { LandingNav, NavSentinel } from "@/components/landing/landing-nav";
import { SiteFooter } from "@/components/landing/site-footer";
import { posts } from "@/lib/blog";
import { pageMetadata } from "@/lib/site";
import styles from "./blog.module.css";

export const metadata: Metadata = pageMetadata({
  title: "Blog",
  description:
    "Notes from the Open Books team on proven financial JSON, typed refusals and connecting AI agents over MCP.",
  path: "/blog",
});

export default function BlogIndexPage() {
  return (
    <div className="lp-page">
      <NavSentinel />
      <LandingNav />
      <main id="content" className={styles.page}>
        <h1 className={styles.heading}>Open Books blog</h1>
        <p className={styles.lede}>
          Notes on proven financial JSON, typed refusals and connecting AI agents over MCP.
        </p>
        <ul className={styles.list}>
          {posts.map((post) => (
            <li key={post.slug}>
              <Link href={`/blog/${post.slug}`} className={styles.card}>
                <span className={styles.meta}>
                  <time dateTime={post.date}>{post.date}</time> · {post.readMinutes} min read
                </span>
                <h2 className={styles.cardTitle}>{post.title}</h2>
                <p className={styles.cardText}>{post.description}</p>
              </Link>
            </li>
          ))}
        </ul>
      </main>
      <SiteFooter />
    </div>
  );
}
