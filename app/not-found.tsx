import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <div className="eyebrow">404</div>
      <h1 className="mt-1 text-[18px] font-semibold">This page does not exist</h1>
      <p className="muted mt-1 text-[12.5px]">Search for a symbol with Ctrl K, or go back to the overview.</p>
      <Link href="/" className="btn btn-primary mt-4">Overview</Link>
    </div>
  );
}
