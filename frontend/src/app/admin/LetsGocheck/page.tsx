import type { Metadata } from "next";

/** Blank screen, reachable only by typing its URL. Nothing links to it. */
export const metadata: Metadata = {
  title: " ",
  robots: { index: false, follow: false },
};

export default function BlankPage() {
  return <div className="fixed inset-0 bg-white" />;
}
