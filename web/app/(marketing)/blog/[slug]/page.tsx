import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LandingNav, NavSentinel } from "@/components/landing/landing-nav";
import { SiteFooter } from "@/components/landing/site-footer";
import { StructuredData } from "@/components/structured-data";
import { getPost, posts } from "@/lib/blog";
import { pageMetadata, siteUrl } from "@/lib/site";
import styles from "../blog.module.css";

type PostPageProps = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return posts.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PostPageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return {};
  return pageMetadata({ title: post.title, description: post.description, path: `/blog/${post.slug}` });
}

export default async function BlogPostPage({ params }: PostPageProps) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  return (
    <div className="lp-page">
      <NavSentinel />
      <LandingNav />
      <main id="content" className={styles.page}>
        <Link href="/blog" className={styles.back}>
          Back to blog
        </Link>
        <header className={styles.article}>
          <span className={styles.meta}>
            <time dateTime={post.date}>{post.date}</time> · {post.readMinutes} min read
          </span>
          <h1 className={styles.heading}>{post.title}</h1>
          <p className={styles.lede}>{post.description}</p>
        </header>
        <article className={styles.article}>
          {post.blocks.map((block, index) => (
            <section key={block.heading ?? index} className={styles.article}>
              {block.heading ? <h2>{block.heading}</h2> : null}
              {block.paragraphs.map((text) => (
                <p key={text}>{text}</p>
              ))}
              {block.bullets ? (
                <ul>
                  {block.bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </article>
        <Link href={post.cta.href} className={`btn btn-primary-landing ${styles.cta}`}>
          {post.cta.label}
        </Link>
        <aside aria-labelledby="sources-heading" className={styles.sources}>
          <h2 id="sources-heading">Sources</h2>
          <ul>
            {post.sources.map((source) => (
              <li key={source.url}>
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.label}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      </main>
      <SiteFooter />
      <StructuredData
        data={{
          "@context": "https://schema.org",
          "@type": "BlogPosting",
          headline: post.title,
          description: post.description,
          datePublished: post.date,
          url: new URL(`/blog/${post.slug}`, siteUrl).href,
          publisher: { "@type": "Organization", name: "Lumeo", url: siteUrl.href },
        }}
      />
    </div>
  );
}
