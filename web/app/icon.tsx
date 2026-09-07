import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

// Generated favicon — the eyebrow rule + "S" mark from the Ledger design
// system (paper ground, near-black ink), so the browser tab reads as the
// same document even before the page loads.
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#11110f",
        }}
      >
        <div
          style={{
            display: "flex",
            color: "#f2efe8",
            fontSize: 20,
            fontWeight: 800,
            fontFamily: "Georgia, serif",
            fontStyle: "italic",
          }}
        >
          S
        </div>
      </div>
    ),
    { ...size }
  );
}
