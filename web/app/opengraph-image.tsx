import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{
      display: "flex", flexDirection: "column", justifyContent: "space-between",
      width: "100%", height: "100%", padding: 76,
      background: "#10160e", color: "#f1f5eb",
      borderTop: "12px solid #afe78f",
    }}>
      <div style={{ display: "flex", fontSize: 28, color: "#afe78f" }}>Developer tools by Lumeo</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", fontSize: 112, fontWeight: 700 }}>Open Books</div>
        <div style={{ display: "flex", fontSize: 36 }}>Financial documents to verified JSON</div>
      </div>
      <div style={{ display: "flex", fontSize: 23, color: "#b4c4aa" }}>Python · Node.js · CLI · Workspace</div>
    </div>,
    size,
  );
}
