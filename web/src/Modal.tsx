import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

/** One focus boundary for import, comparison and destructive-action dialogs. */
export default function Modal({
  children,
  onClose,
  labelledBy,
  className = "",
}: {
  children: React.ReactNode;
  onClose: () => void;
  labelledBy: string;
  className?: string;
}) {
  const dialog = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const scrollBefore = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current!;
    const portal = element.parentElement!;
    const siblings = [...document.body.children].filter(
      (node) => node !== portal,
    );
    const inertBefore = siblings.map((node) => node.hasAttribute("inert"));
    siblings.forEach((node) => node.setAttribute("inert", ""));
    const focusables = () =>
      [
        ...element.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
        ),
      ].filter(
        (node) =>
          !node.closest("[hidden]") && node.getAttribute("type") !== "hidden",
      );
    (
      element.querySelector<HTMLElement>("[data-autofocus]") ||
      focusables()[0] ||
      element
    ).focus();
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close.current();
      }
      if (event.key !== "Tab") return;
      const targets = focusables();
      if (!targets.length) {
        event.preventDefault();
        element.focus();
        return;
      }
      const first = targets[0],
        last = targets[targets.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !element.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !element.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handle, true);
    return () => {
      document.body.style.overflow = scrollBefore;
      document.removeEventListener("keydown", handle, true);
      siblings.forEach((node, index) => {
        if (!inertBefore[index]) node.removeAttribute("inert");
      });
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialog}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className={`workbench-modal ${className}`}
      >
        {children}
      </section>
    </div>,
    document.body,
  );
}
