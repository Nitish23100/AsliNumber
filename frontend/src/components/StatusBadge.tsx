/**
 * Shared primitive per docs/design.md §12 and §5 (Component rules):
 * icon (16px, status color) + text label (never abbreviated) + a 2px
 * left border in the status color. Not a filled gradient pill — color
 * never carries meaning alone (docs/design.md §8), so `label` is
 * required, not optional.
 *
 * Reused by the Login page's post-login status indicators (Requirement
 * 12.5: API reachability, Mongo connectivity, authenticated role, each
 * shown as its own badge rather than a single middle-dot-joined string —
 * see requirements.md's note on Requirement 12 for why).
 */

export type StatusTone = "neutral" | "positive" | "negative";

const TONE_BORDER_CLASS: Record<StatusTone, string> = {
  neutral: "border-ink-soft",
  positive: "border-verified-official",
  negative: "border-high-risk-review",
};

const TONE_ICON_CLASS: Record<StatusTone, string> = {
  neutral: "text-ink-soft",
  positive: "text-verified-official",
  negative: "text-high-risk-review",
};

export interface StatusBadgeProps {
  /** A Font Awesome icon class, e.g. "fa-solid fa-circle-check". */
  icon: string;
  label: string;
  tone?: StatusTone;
}

export function StatusBadge({ icon, label, tone = "neutral" }: StatusBadgeProps) {
  return (
    <div
      className={`flex items-center gap-8 border-l-2 pl-8 py-4 ${TONE_BORDER_CLASS[tone]}`}
      role="status"
    >
      <i
        className={`${icon} ${TONE_ICON_CLASS[tone]}`}
        aria-hidden="true"
        style={{ fontSize: 16 }}
      />
      <span className="text-body text-ink">{label}</span>
    </div>
  );
}
