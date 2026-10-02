import React, { useId, useLayoutEffect, useRef, useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

// Supplemental tooltips live outside the drawer's scrolling/clipping parents.
export default function IconButton({ label, children, className = '', ...props }) {
  const id = useId();
  const anchor = useRef(null);
  const timer = useRef(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const show = () => { clearTimeout(timer.current); setOpen(true); };
  const hide = () => { timer.current = setTimeout(() => setOpen(false), 120); };
  useEffect(() => () => clearTimeout(timer.current), []);
  useLayoutEffect(() => {
    if (!open || !anchor.current) return;
    const rect = anchor.current.getBoundingClientRect();
    setPosition({ left: Math.min(window.innerWidth - 110, Math.max(110, rect.left + rect.width / 2)),
      top: rect.top > 60 ? rect.top - 8 : rect.bottom + 8,
      transform: rect.top > 60 ? 'translate(-50%, -100%)' : 'translateX(-50%)' });
    const close = () => setOpen(false);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => { window.removeEventListener('scroll', close, true); window.removeEventListener('resize', close); };
  }, [open, label]);
  return <>
    <button {...props} ref={anchor} type={props.type || 'button'} className={`hriday-icon-button ${className}`}
      aria-label={label} aria-describedby={open ? id : undefined}
      onPointerEnter={show} onPointerLeave={hide} onFocus={show} onBlur={hide}
      onKeyDown={event => {
        if (event.key === 'Escape' && open) { event.stopPropagation(); clearTimeout(timer.current); setOpen(false); }
        props.onKeyDown?.(event);
      }}>{children}</button>
    {open && position && createPortal(<div id={id} role="tooltip" className="hriday-tooltip" style={position}
      onPointerEnter={() => clearTimeout(timer.current)} onPointerLeave={hide}>{label}</div>, document.body)}
  </>;
}
