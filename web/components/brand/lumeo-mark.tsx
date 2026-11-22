import Image from "next/image";

const RATIO = 185 / 196;

export function LumeoMark({ size = 40, className = "", priority = false }: { size?: number; className?: string; priority?: boolean }) {
  const w = Math.round(size * RATIO);
  const common = {
    width: w,
    height: size,
    alt: "",
    "aria-hidden": true as const,
    priority,
    loading: priority ? undefined : ("eager" as const),
    style: { width: w, height: size },
  };
  return (
    <span className={`inline-flex shrink-0 items-center ${className}`} style={{ width: w, height: size }}>
      <Image {...common} src="/brand/mark-white.png" className="brand-asset--dark" />
      <Image {...common} src="/brand/mark-black.png" className="brand-asset--light" />
    </span>
  );
}
