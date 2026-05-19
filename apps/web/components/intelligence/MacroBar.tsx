"use client";

interface MacroItem {
  price: number | null;
  change_pct: number | null;
}

interface Props {
  data: Record<string, MacroItem> | undefined;
}

export function MacroBar({ data }: Props) {
  if (!data) return null;

  return (
    <div className="flex gap-4 overflow-x-auto pb-1 scrollbar-hide">
      {Object.entries(data).map(([label, item]) => (
        <div key={label} className="flex items-center gap-2 shrink-0 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
          <span className="text-xs text-gray-400 font-medium">{label}</span>
          {item.price !== null && (
            <>
              <span className="text-sm font-semibold">{item.price}</span>
              {item.change_pct !== null && (
                <span className={`text-xs font-medium ${item.change_pct >= 0 ? "positive" : "negative"}`}>
                  {item.change_pct >= 0 ? "+" : ""}{item.change_pct}%
                </span>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
