import { useState, type ReactNode } from "react";
import { Segmented } from "../ui/segmented";

export type CellTab = { id: string; label: string; count?: number; content: ReactNode; desktopOnly?: boolean };

type Props = { id: string; title: string; meta?: ReactNode; tabs?: CellTab[]; children?: ReactNode; className?: string };

/**
 * One cell of the Home grid. The grid fits the screen, so each cell scrolls inside its body;
 * counts sit in the header so nothing important hides below the fold.
 */
export function HomeCell({ id, title, meta, tabs, children, className = "" }: Props) {
  const [active, setActive] = useState(tabs?.[0]?.id ?? "");
  const current = tabs?.find((tab) => tab.id === active);

  return (
    <section className={`card home-cell ${tabs ? "home-cell--tabbed" : ""} ${className}`} aria-labelledby={`${id}-title`}>
      <div className="home-cell__head">
        <h2 id={`${id}-title`} className="section-title">
          {title}
        </h2>
        {meta && <span className="card__meta home-cell__meta">{meta}</span>}
        {tabs && (
          <Segmented className="home-cell__tabs" role="tablist" aria-label={title}>
            {tabs.map((tab) => (
              <button key={tab.id} type="button" role="tab" className={tab.desktopOnly ? "segmented__option home__desktop-only" : "segmented__option"} aria-selected={tab.id === active} aria-pressed={tab.id === active} onClick={() => setActive(tab.id)}>
                {tab.label}
                {tab.count !== undefined && <span className="home-cell__count"> {tab.count}</span>}
              </button>
            ))}
          </Segmented>
        )}
      </div>
      <div className="home-cell__body" role={tabs ? "tabpanel" : undefined} aria-label={current?.label}>
        {current ? (
          // Keyed by tab so each switch mounts fresh and replays the fade.
          <div className="home-cell__panel" key={current.id}>
            {current.content}
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

