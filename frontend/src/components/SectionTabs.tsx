import type { LucideIcon } from "lucide-react";

export type SectionTab = {
  id: string;
  label: string;
  count?: number;
  icon?: LucideIcon;
};

export const sectionTabId = (panelId: string, id: string) =>
  `${panelId}-tab-${id || "all"}`;

export default function SectionTabs({
  label,
  panelId,
  items,
  value,
  onChange,
}: {
  label: string;
  panelId: string;
  items: SectionTab[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="section-tabs" role="tablist" aria-label={label}>
      {items.map(({ id, label: itemLabel, count, icon: Icon }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={value === id}
          aria-controls={panelId}
          tabIndex={value === id ? 0 : -1}
          className="section-tab"
          onClick={() => onChange(id)}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const offset = event.key === "ArrowRight" ? 1 : -1;
            const index = items.findIndex((item) => item.id === id);
            const next =
              items[
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? items.length - 1
                    : (index + offset + items.length) % items.length
              ];
            onChange(next.id);
            document.getElementById(sectionTabId(panelId, next.id))?.focus();
          }}
          id={sectionTabId(panelId, id)}
        >
          {Icon && <Icon size={16} aria-hidden="true" />}
          <span>{itemLabel}</span>
          {typeof count === "number" && (
            <span className="section-tab-count">{count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
