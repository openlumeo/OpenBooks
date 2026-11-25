export type BlogBlock = { heading?: string; paragraphs: string[]; bullets?: string[] };

export type BlogSource = { label: string; url: string };

export type BlogPost = {
  slug: string;
  title: string;
  description: string;
  date: string;
  readMinutes: number;
  blocks: BlogBlock[];
  sources: BlogSource[];
  cta: { label: string; href: string };
};

export const posts: BlogPost[] = [
  {
    slug: "why-open-books-refuses",
    title: "Your bank statement parser should be allowed to say no",
    description:
      "A wrong number that looks right is worse than no number. Here is why Open Books releases a file only when its own arithmetic proves it.",
    date: "2026-11-25",
    readMinutes: 4,
    blocks: [
      {
        paragraphs: [
          "Picture a statement where 21,429,000 is read as 21,829,000. One digit. Every column still lines up, the JSON is valid, and nothing in the pipeline complains. That is not a made-up scenario: it is an example from FinCriticalED, a 2025 benchmark of fact-level OCR on financial documents.",
          "Most parsers answer every file. The wrong answers arrive looking exactly like the right ones, and you find out weeks later when a reconciliation will not close.",
        ],
      },
      {
        heading: "Fluent is not the same as correct",
        paragraphs: [
          "Language models are good at reading a table and bad at being trusted with its arithmetic. The FAITH study on S&P 500 annual reports found that even frontier models show 10 to 20 percent error rates on multi-step numerical reasoning over financial tables.",
          "A bank statement is the one place you can skip the guessing. It prints its own answer key: an opening balance, a closing balance, and a running total that has to agree with both.",
        ],
      },
      {
        heading: "The rule: prove it or refuse it",
        paragraphs: [
          "Open Books runs every file through detect, parse, normalise, balance and validate. A file is released only when every balance check ties out against figures printed in the file itself.",
        ],
        bullets: [
          "Pass: you get one openbooks.v1 JSON document, proven against the file's own totals.",
          "Fail: you get a typed refusal that names the reason, and no data at all.",
          "Never: a plausible number the file does not support.",
        ],
      },
      {
        heading: "A refusal is a feature",
        paragraphs: [
          "A refusal is cheap to handle. Fix the input, supply the missing opening balance, or send the file to a person. A silent wrong number is expensive, because nobody knows to look for it.",
          "The same rule holds when you ask questions. The model never adds money. It calls tools, TypeScript does the sums in decimal arithmetic over released documents only, and refused files are skipped instead of estimated.",
        ],
      },
    ],
    sources: [
      { label: "FAITH: Assessing Intrinsic Tabular Hallucinations in Finance (arXiv, 2025)", url: "https://arxiv.org/abs/2508.05201" },
      { label: "FinCriticalED: A Visual Benchmark for Financial Fact-Level OCR (arXiv, 2025)", url: "https://arxiv.org/pdf/2511.14998" },
    ],
    cta: { label: "See how verification works", href: "/docs/how-verification-works" },
  },
  {
    slug: "connect-your-ai-agent-with-mcp",
    title: "Give your AI agent a ledger it can trust, in one command",
    description:
      "Add the Open Books MCP server to Claude, Cursor, Codex and more, then verify a real statement from a local folder in minutes.",
    date: "2026-11-25",
    readMinutes: 3,
    blocks: [
      {
        paragraphs: [
          "MCP stopped being a niche idea fast. When Anthropic donated the Model Context Protocol to the Linux Foundation's Agentic AI Foundation in December 2025, it reported more than 10,000 active public servers and over 97 million monthly SDK downloads. Vendor-reported figures, but the direction is clear: agents now reach for tools, not guesses.",
          "Finance is where that matters most. An agent that can read a statement is useful. An agent that can only return a statement that proved itself is safe to put in a workflow.",
        ],
      },
      {
        heading: "One command to connect",
        paragraphs: [
          "The server ships in the npm package @lumeo_hq/openbooks as the openbooks-mcp bin. It needs Node.js 20 or newer and runs over stdio, so your client starts it as a subprocess.",
        ],
        bullets: [
          "Claude Code: claude mcp add openbooks -- npx -y -p @lumeo_hq/openbooks openbooks-mcp",
          "Codex: codex mcp add openbooks -- npx -y -p @lumeo_hq/openbooks openbooks-mcp",
          "Claude Desktop, Cursor, Cline, Gemini CLI: an mcpServers entry with command npx and the same arguments.",
        ],
      },
      {
        heading: "Check it works before you trust it",
        paragraphs: [
          "Ask your agent to run the doctor operation. It reports whether the Python engine is installed. If it is missing, run npx -y @lumeo_hq/openbooks install-engine --scan.",
          "To let the agent read files from one folder, add --root with that folder's path. The process_file tool appears only when a root is set, so the agent sees nothing you did not choose to share.",
        ],
      },
      {
        heading: "What your agent gets back",
        paragraphs: [
          "For each file: one proven JSON document, or a typed refusal that says why. Your agent can act on the first and explain the second, with no number left to second-guess.",
        ],
      },
    ],
    sources: [
      { label: "Anthropic: Donating the Model Context Protocol to the Agentic AI Foundation", url: "https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation" },
    ],
    cta: { label: "Connect your agent", href: "/get-started" },
  },
  {
    slug: "the-hidden-cost-of-month-end-reconciliation",
    title: "Month-end close is not slow because your team is slow",
    description:
      "Teams lose days re-keying bank data and chasing mismatches. The fix is not working harder, it is trusting the input.",
    date: "2026-11-25",
    readMinutes: 3,
    blocks: [
      {
        paragraphs: [
          "Ledge's 2025 month-end close benchmarks report that many finance teams spend 20 to 50 hours a month on cash reconciliation, and that half need six or more business days to close the books. Those are survey figures from a software vendor, so read them as a ballpark, not a law.",
          "Still, ask anyone who has done a close and the shape is familiar: the hours do not go on judgement, they go on checking whether the data can be believed.",
        ],
      },
      {
        heading: "Where the hours actually go",
        paragraphs: ["The time sink is rarely the matching itself. It is everything wrapped around it:"],
        bullets: [
          "Re-keying figures from PDFs and exports into a spreadsheet.",
          "Hunting a one-digit difference through hundreds of rows.",
          "Not knowing whether a mismatch is a real discrepancy or a parsing slip.",
        ],
      },
      {
        heading: "Trust the input, then match",
        paragraphs: [
          "If every file arrives already proven against its own opening and closing balances, a mismatch can only mean one thing: something real. The question changes from is this data right to what does this difference mean.",
          "That is the bet behind Open Books. Prove the file first. Refuse it loudly when it cannot be proven. Spend your hours on the exceptions that need a human.",
        ],
      },
      {
        heading: "Try it on a real statement",
        paragraphs: [
          "Upload a bank statement in the workspace, or point your AI agent at a folder. You will get proven JSON, or a refusal that tells you exactly what is missing.",
        ],
      },
    ],
    sources: [
      { label: "Ledge: Month-end close benchmarks for 2025", url: "https://ledge.co/content/month-end-close-benchmarks-for-2025" },
    ],
    cta: { label: "Open the workspace", href: "/app" },
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return posts.find((post) => post.slug === slug);
}
