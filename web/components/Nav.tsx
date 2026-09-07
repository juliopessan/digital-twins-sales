"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Persistent top bar so there's always a way back to Setup — the app
 * previously had no navigation at all between the Setup and Results
 * screens once you'd moved forward. */
export default function Nav() {
  const pathname = usePathname();
  const onResults = pathname?.startsWith("/runs") ?? false;

  return (
    <div className="nav">
      <div className="nav-inner">
        <Link href="/" className="nav-brand">
          Sales Digital Twins
        </Link>
        {onResults && (
          <Link href="/" className="nav-back">
            ← New simulation
          </Link>
        )}
      </div>
    </div>
  );
}
