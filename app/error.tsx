"use client";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <div className="eyebrow">Error</div>
      <h1 className="mt-1 text-[18px] font-semibold">Something went wrong on this page</h1>
      <p className="muted mt-1 text-[12.5px]">{error.message || "An unexpected error occurred."}</p>
      <button className="btn btn-primary mt-4" onClick={reset}>Try again</button>
    </div>
  );
}
