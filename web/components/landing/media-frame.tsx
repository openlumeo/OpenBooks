"use client";

// Looping render inside a laptop frame. The video is muted and playsInline, and it has the
// autoPlay attribute only when motion is allowed. While motion is allowed it plays only while
// on screen. With reduced motion, or without JS, the poster is the picture. The frame reserves
// its 16:10 screen up front, so the video never shifts the layout.
import { useEffect, useRef, useState } from "react";
import { DeviceFrame } from "./device-frame";
import styles from "./media-frame.module.css";

const REDUCED = "(prefers-reduced-motion: reduce)";

export type LoopSource = { src: string; type: string };

export type LoopFrameProps = {
  poster: string;
  /** Webm first, then mp4. */
  sources: readonly LoopSource[];
  /** Visually hidden text alternative for assistive tech. */
  label: string;
  /** Visible caption under the frame. */
  caption: string;
};

export function LoopFrame({ poster, sources, label, caption }: LoopFrameProps) {
  const ref = useRef<HTMLVideoElement>(null);
  const [autoPlay, setAutoPlay] = useState(false);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;

    if (window.matchMedia(REDUCED).matches) {
      video.pause();
      return;
    }
    setAutoPlay(true);

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting) void video.play().catch(() => undefined);
        else video.pause();
      },
      { threshold: 0.25 },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  return (
    <DeviceFrame variant="laptop" label={caption}>
      <video
        ref={ref}
        className={styles.video}
        muted
        loop
        playsInline
        autoPlay={autoPlay}
        preload="metadata"
        poster={poster}
        aria-hidden="true"
      >
        {sources.map((source) => (
          <source key={source.src} src={source.src} type={source.type} />
        ))}
      </video>
      <span className="sr-only">{label}</span>
    </DeviceFrame>
  );
}
