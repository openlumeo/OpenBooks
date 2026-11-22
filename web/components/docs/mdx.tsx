import defaultComponents from "fumadocs-ui/mdx";
import { SketchCallout as Callout } from "./sketch-callout";
import { Card, Cards } from "fumadocs-ui/components/card";
import { Step, Steps } from "fumadocs-ui/components/steps";
import { Tab, Tabs } from "fumadocs-ui/components/tabs";
import type { MDXComponents } from "mdx/types";
import { SampleTerminal } from "./sample-terminal";
import { AgentOnboarding } from "./agent-onboarding";

export const docsComponents = {
  ...defaultComponents, Callout, Card, Cards, Step, Steps, Tab, Tabs, SampleTerminal, AgentOnboarding,
} satisfies MDXComponents;
