import Link from "next/link";
import { Instrument_Serif } from "next/font/google";
import s from "@/app/landing.module.css";
import { ArchGlyph, SealGlyph } from "./ornaments";
import { SubscribeForm } from "./subscribe-form";

const serif = Instrument_Serif({ weight: "400", subsets: ["latin"], variable: "--font-display", display: "swap" });

const FORMATS = ["CSV", "OFX", "MT940", "PDF", "Scans", "XLSX", "Stripe", "Razorpay", "PayPal", "Wise", "Form 26AS", "AIS", "1099-B"] as const;

const READS = [
  { term: "Bank statements", text: "CSV, OFX, MT940, PDF and scanned pages, read into one shape with every figure tied to its source." },
  { term: "Payment gateways", text: "Stripe, Razorpay, PayPal and Wise settlements, proven line by line against what they claim to pay out." },
  { term: "Tax and ledger documents", text: "26AS, AIS, FIRA, 1099-B and trial balances, checked by arithmetic before anything is released." },
  { term: "Reconciliation", text: "Link a gateway payout to the bank credit it became, so the books close without a spreadsheet hunt." },
] as const;

const STEPS = [
  { title: "Detect", text: "Recognise the layout before reading a single number." },
  { title: "Parse", text: "Keep the page, box and raw text behind every field." },
  { title: "Normalise", text: "One date, currency and sign convention. Ambiguous day and month order is proven, never assumed." },
  { title: "Prove", text: "Opening plus movement must equal closing, or the file is refused." },
] as const;

const LEDGER = Array.from({ length: 24 }, (_, i) => {
  const day = String(((i * 7) % 28) + 1).padStart(2, "0");
  const amt = ((((i * 7919) % 90000) / 100) + 120).toFixed(2);
  const bal = ((((i * 104729) % 9000000) / 100) + 5000).toFixed(2);
  return `${day}/04/26  NEFT-CR  ${String(i * 37 + 1000)}  ${amt.padStart(9)}  BAL ${bal.padStart(11)}  TIES   `.repeat(3);
}).join("\n");

export function Landing() {
  return (
    <div className={`${serif.variable} ${s.page}`}>
      <div className={s.wrap}>
        <header className={s.nav}>
          <Link href="/" className={`${s.brand} ${s.display}`}>Open Books</Link>
          <nav className={s.navLinks} aria-label="Main">
            <a className={`${s.navLink} ${s.navHide}`} href="#reads">Platform</a>
            <a className={`${s.navLink} ${s.navHide}`} href="#how">How it works</a>
            <Link className={s.navLink} href="/auth/sign-in">Sign in</Link>
            <Link className={`${s.btn} ${s.btnDark}`} href="/app">Open workspace</Link>
          </nav>
        </header>

        <section className={s.hero} aria-labelledby="hero-title">
          <div className={`${s.ledgerBg} ${s.mono}`} aria-hidden="true">{LEDGER}</div>
          <div className={`${s.heroCard} ${s.heroLeft}`} aria-hidden="true">
            <span className={s.mono}>statement.pdf</span>
            <i /><i /><i /><i />
            <b className={s.mono}>BAL 1,31,150.00</b>
          </div>
          <div className={`${s.heroCard} ${s.heroRight} ${s.mono}`} aria-hidden="true">
            <span>{"{"}</span>
            <span>&nbsp;&nbsp;&quot;status&quot;: &quot;ok&quot;,</span>
            <span>&nbsp;&nbsp;&quot;ties_out&quot;: true</span>
            <span>{"}"}</span>
          </div>
          <div className={s.arc} aria-hidden="true">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <span key={i} className={s.coin} style={{ ["--i" as string]: i }}><SealGlyph /></span>
            ))}
          </div>

          <h1 id="hero-title" className={`${s.h1} ${s.display}`}>Statements in. One proven JSON out.</h1>
          <p className={s.lede}>
            Open Books reads bank statements, gateway settlements and tax documents, checks every balance, and releases a single JSON file.
            When the numbers don&rsquo;t tie out, it refuses in plain terms instead of guessing.
          </p>
          <div className={s.ctaRow}>
            <Link className={`${s.btn} ${s.btnDark}`} href="/app">Try it on a statement</Link>
            <a className={`${s.btn} ${s.btnGhost}`} href="#demo">Watch the demo</a>
          </div>
          <ul className={s.formats} aria-label="Supported formats">
            {FORMATS.map((f) => <li key={f} className={s.mono}>{f}</li>)}
          </ul>
        </section>
      </div>

      <main id="conversation">
        <section id="demo" className={s.section} aria-labelledby="demo-title">
          <div className={s.wrap}>
            <h2 id="demo-title" className={`${s.sectionHead} ${s.display}`}>One file in. Proof or refusal out.</h2>
            <p className={s.sectionSub}>A minute with the real workspace: a statement goes in, every number shows its source, and the file is either released or refused with nothing written.</p>
            <figure className={s.film}>
              <video controls preload="none" playsInline poster="/demo/open-books-demo-poster.jpg" aria-describedby="demo-caption">
                <source src="/demo/open-books-demo.mp4" type="video/mp4" />
                Your browser can&rsquo;t play this video. <a href="/demo/open-books-demo.mp4">Download the demo</a>.
              </video>
              <figcaption id="demo-caption" className={s.filmCaption}>
                Open Books on a bank statement, from upload to a released file. About one minute, with sound.
              </figcaption>
            </figure>
          </div>
        </section>

        <section id="reads" className={s.section} aria-labelledby="reads-title">
          <div className={`${s.wrap} ${s.readsGrid}`}>
            <h2 id="reads-title" className={`${s.sectionHead} ${s.display}`}>Four kinds of document, one standard of proof</h2>
            <dl className={s.readsList}>
              {READS.map((r) => (
                <div key={r.term}>
                  <dt className={s.display}>{r.term}</dt>
                  <dd>{r.text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section id="how" className={s.section} aria-labelledby="how-title">
          <div className={s.wrap}>
            <h2 id="how-title" className={`${s.bigStatement} ${s.display}`}>
              Four checks stand between your upload and the JSON. A file only passes if every one of them does.
            </h2>
            <ol className={s.steps}>
              {STEPS.map((st) => (
                <li key={st.title}>
                  <h3 className={`${s.stepTitle} ${s.display}`}>{st.title}</h3>
                  <p className={s.cardText}>{st.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="proof" className={s.section} aria-labelledby="proof-title">
          <div className={s.wrap}>
            <h2 id="proof-title" className={`${s.sectionHead} ${s.display}`}>Built to say no</h2>
            <p className={`${s.proofText} ${s.display}`}>
              On 69 synthetic test cases, Open Books made the right call every time: it released the 27 clean files, refused the rest, and <em>accepted nothing it should have refused</em>.
            </p>
            <p className={s.fine}>Measured on synthetic statements. No real customer documents were used in these figures.</p>
          </div>
        </section>

        <section className={s.section} aria-label="Principle and training notice">
          <div className={`${s.wrap} ${s.split}`}>
            <div className={s.artTile} aria-hidden="true"><SealGlyph className={s.artSeal} /></div>
            <div className={s.principle}>
              <q className={s.display}>A typed refusal beats a confident guess.</q>
              <p>The model that reads your document can only add doubt. It can raise a refusal, but it can never release a file the arithmetic hasn&rsquo;t already proven.</p>
            </div>
          </div>
          <aside className={`${s.wrap} ${s.notice}`} aria-labelledby="notice-title">
            <h2 id="notice-title" className={`${s.noticeTitle} ${s.display}`}>We&rsquo;re training our model</h2>
            <p>Open Books is in an active training phase, and documents people upload can help improve the model. We will always ask before we keep any of yours for training, and the answer will start as no. Nothing is kept for training without your explicit opt-in.</p>
          </aside>
        </section>

        <section id="subscribe" className={s.section} aria-labelledby="sub-title">
          <div className={`${s.wrap} ${s.subWrap}`}>
            <h2 id="sub-title" className={`${s.sectionHead} ${s.display}`}>Follow the build</h2>
            <SubscribeForm />
          </div>
        </section>

        <section className={`${s.section} ${s.closing}`} aria-labelledby="close-title">
          <div className={`${s.wrap} ${s.closeGrid}`}>
            <div>
              <h2 id="close-title" className={s.display}>Let&rsquo;s build a stronger foundation for your books.</h2>
              <p className={`${s.lede} ${s.ledeLeft}`}>Start with one statement. See the proof for yourself.</p>
              <Link className={`${s.btn} ${s.btnDark}`} href="/app">Try it on a statement</Link>
            </div>
            <ArchGlyph className={s.arch} />
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <div className={`${s.wrap} ${s.footGrid}`}>
          <p className={`${s.footTag} ${s.display}`}>A smarter way to close the books.</p>
          <div className={s.footCol}><h3>Product</h3><Link href="/app">Workspace</Link><a href="#reads">Platform</a><a href="#how">How it works</a></div>
          <div className={s.footCol}><h3>Account</h3><Link href="/auth/sign-in">Sign in</Link><Link href="/auth/sign-up">Create an account</Link></div>
          <div className={s.footCol}><h3>Company</h3><a href="https://lumeo.co.in">Lumeo</a><a href="#subscribe">Updates</a></div>
        </div>
        <div className={`${s.wrap} ${s.legal}`}>&copy; {new Date().getFullYear()} Lumeo. Open Books reads documents; it does not give financial advice.</div>
      </footer>
    </div>
  );
}
