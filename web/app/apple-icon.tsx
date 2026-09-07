import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
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
            fontSize: 110,
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
