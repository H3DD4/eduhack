// ThinkFirst "Mind print" mark: a head in profile with a fingerprint for a mind and a spark (the student's idea).
const HEAD = "M20 58 L20 48 C10 44 6 34 8 24 C11 10 24 4 36 5 C50 6 58 16 58 28 C58 32 60 35 62 38 C63 40 61 41 59 41 L57 41 L57 46 C57 50 54 52 50 52 L44 52 L44 58 Z";
const SPARK = "M30 19.5 C30.8 23.6 31.9 24.7 36 26 C31.9 27.3 30.8 28.4 30 32.5 C29.2 28.4 28.1 27.3 24 26 C28.1 24.7 29.2 23.6 30 19.5 Z";

type Variant = "light" | "dark" | "mono";

export function Mark({ size = 36, variant = "light", simple, title, className = "" }:
  { size?: number; variant?: Variant; simple?: boolean; title?: string; className?: string }) {
  const stroke = variant === "dark" ? "#FFFBF3" : "#0F172A";
  const fill = variant === "mono" ? "none" : "#25D366";
  const small = simple ?? size <= 28;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className}
      role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      <g transform="translate(-2 0)">
        {variant === "light" && <path d={HEAD} transform="translate(3 3)" fill="#0F172A" />}
        <path d={HEAD} fill={fill} stroke={stroke} strokeWidth={3} strokeLinejoin="round" />
        {!small && (
          <>
            <circle cx="30" cy="26" r="10.5" fill="none" stroke="#0F172A" strokeWidth="2.6" strokeLinecap="round" strokeDasharray="46 8 10 7" transform="rotate(-30 30 26)" />
            <circle cx="30" cy="26" r="15.5" fill="none" stroke="#0F172A" strokeWidth="2.6" strokeLinecap="round" strokeDasharray="62 9 18 8" transform="rotate(40 30 26)" />
          </>
        )}
        <path d={SPARK} fill={variant === "mono" ? "#0F172A" : "#DCF8C6"} stroke="#0F172A" strokeWidth="1.6" strokeLinejoin="round" />
      </g>
      {!small && (
        <>
          <circle cx="57" cy="7" r="3.4" fill="#25D366" stroke="#0F172A" strokeWidth="2" />
          <circle cx="62" cy="13" r="1.6" fill="#0F172A" />
        </>
      )}
    </svg>
  );
}

export function Logo({ size = 34, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2" style={{ fontSize: Math.round(size * 0.62) }}>
      <Mark size={size} variant={dark ? "dark" : "light"} />
      <span className={dark ? "text-white" : "text-ink"}>
        Think<span className="ml-0.5 rounded-[0.3em] border-2 border-ink bg-hl px-1.5 text-ink">First</span>
      </span>
    </span>
  );
}
