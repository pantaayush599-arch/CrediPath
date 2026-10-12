import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel p-6">
      <div className="font-medium">Page not found</div>
      <p className="mt-1 text-sm text-ink-2">
        <Link href="/" className="text-accent underline">Back to the overview</Link>
      </p>
    </div>
  );
}
