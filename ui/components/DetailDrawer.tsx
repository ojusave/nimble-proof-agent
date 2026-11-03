'use client';
import {useEffect, useRef, type ReactNode} from 'react';
import {X} from 'lucide-react';

export function DetailDrawer({id, title, subtitle, children, onClose}: {id: string; title: string; subtitle: string; children: ReactNode; onClose(): void}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const overflow = document.body.style.overflow;
    dialog.showModal(); document.body.style.overflow = 'hidden';
    return () => {dialog.close(); document.body.style.overflow = overflow;};
  }, []);
  return <dialog ref={ref} className="detail-drawer" aria-labelledby={id + '-title'} onCancel={event => {event.preventDefault(); onClose();}}
    onClick={event => {if (event.target === event.currentTarget) {const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();}}}>
    <header className="drawer-header"><div><p>{subtitle}</p><h2 id={id + '-title'}>{title}</h2></div><button className="icon-button" aria-label="Close evidence" onClick={onClose} autoFocus><X size={20}/></button></header>
    <div className="drawer-body">{children}</div>
  </dialog>;
}
