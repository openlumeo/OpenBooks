import { Section } from "./section";
import { InputBoxes } from "./inputs-boxes";

export function Inputs() {
  return (
    <Section id="inputs" heading="The files your clients actually send.">
      <p className="t-lede">
        Bank statements, gateway settlements, tax records and workpapers, in the formats they arrive in. Up to 20 MB per
        file.
      </p>
      <InputBoxes />
    </Section>
  );
}
