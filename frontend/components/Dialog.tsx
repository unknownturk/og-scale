"use client";
import { useEffect, useRef } from "react";

export function Dialog({ title, intro, wide, onClose, children, footer }: {
  title: string;
  intro?: string;
  wide?: boolean;
  onClose: () => void;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el && !el.open) el.showModal();
  }, []);
  return (
    <dialog ref={ref} className={`fenster${wide ? " breit" : ""}`} onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="fenster-kopf">
        <h2>{title}</h2>
        {intro && <p className="leise">{intro}</p>}
      </div>
      <div className="fenster-inhalt">{children}</div>
      <div className="fenster-fuss">{footer}</div>
    </dialog>
  );
}
