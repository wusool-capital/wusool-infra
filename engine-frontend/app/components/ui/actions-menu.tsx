import { CaretDown, DotsThree } from "@phosphor-icons/react";
import { useState } from "react";
import { createPortal } from "react-dom";
import { useAnchored } from "./use-anchored";
import { useDismiss } from "./use-dismiss";

// disabled: shown but not clickable, for an action that does not apply to this item.
export type MenuAction<P extends string> = { panel: P; label: string; disabled?: boolean };

type Props<P extends string> = {
  itemName: string;
  actions: readonly MenuAction<P>[];
  onPick: (panel: P) => void;
  /** "row" in tables (28px), "header" beside drawer buttons (36px). */
  size?: "row" | "header";
  /** A text button in place of "...", for a single action that needs a choice (Add to deal, then the project). */
  label?: string;
  disabled?: boolean;
};

// The "..." menu keeps each row action at 3 clicks: menu, action, then Save, Add or Send.
// It is a menu, not a dialog, so it does not count as a second layer. It opens at page level
// (see useAnchored) so a scrolling table cannot cut it off.
export function ActionsMenu<P extends string>({ itemName, actions, onPick, size = "row", label, disabled }: Props<P>) {
  const [open, setOpen] = useState(false);
  const dismiss = useDismiss<HTMLDivElement, HTMLUListElement>(open, () => setOpen(false));
  const anchor = useAnchored(open, () => setOpen(false), label ? "start" : "end");

  return (
    <div
      className="chip-menu"
      onClick={(event) => event.stopPropagation()}
      ref={dismiss.ref}
      onBlur={dismiss.onBlur}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        className={label ? "button button--small button--quiet" : `icon-button icon-button--${size}`}
        disabled={disabled}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={label ? undefined : `Actions for ${itemName}`}
        ref={anchor.triggerRef}
        onClick={() => {
          anchor.place();
          setOpen(!open);
        }}
      >
        {label ? (
          <>
            {label} <CaretDown size={12} aria-hidden="true" />
          </>
        ) : (
          <DotsThree size={size === "row" ? 18 : 20} weight="bold" aria-hidden="true" />
        )}
      </button>
      {open &&
        createPortal(
        <ul ref={dismiss.panelRef} className={`chip-menu__list ${label ? "" : "chip-menu__list--end "}chip-menu__list--fixed`} style={anchor.style} onClick={(event) => event.stopPropagation()}>
          {actions.map((action) => (
            <li key={action.panel}>
              <button
                type="button"
                className="chip-menu__option"
                disabled={action.disabled}
                onClick={() => {
                  setOpen(false);
                  onPick(action.panel);
                }}
              >
                {action.label}
              </button>
            </li>
          ))}
        </ul>,
          document.body,
        )}
    </div>
  );
}
