import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import AnimatedAcousticOrb from './presentation/AnimatedAcousticOrb.jsx';
import HRIDAYChat from './hriday/HRIDAYChat.jsx';

export function useChatViewport() {
  const read = () => ({
    mobile: window.matchMedia('(max-width: 600px)').matches,
    height: window.visualViewport?.height || window.innerHeight,
    top: window.visualViewport?.offsetTop || 0,
  });
  const [viewport, setViewport] = useState(read);
  useEffect(() => {
    const update = () => setViewport(read());
    window.addEventListener('resize', update);
    window.visualViewport?.addEventListener('resize', update);
    window.visualViewport?.addEventListener('scroll', update);
    return () => {
      window.removeEventListener('resize', update);
      window.visualViewport?.removeEventListener('resize', update);
      window.visualViewport?.removeEventListener('scroll', update);
    };
  }, []);
  return viewport;
}

export function hiddenChatScope({ activeDatasetId, activeSheetId, activeSnapshotId, activePage }) {
  const sheetId = Number(new URLSearchParams(window.location.search).get('sheet_id'));
  return {
    datasetId: activeDatasetId ?? null,
    sheetId: activeSheetId ?? (Number.isSafeInteger(sheetId) && sheetId > 0 ? sheetId : null),
    snapshotId: activeSnapshotId ?? null,
    page: activePage ?? null,
  };
}

export default function GlobalCopilotWidget({
  isOpen = false, onToggle, onClose,
  activeDatasetId = null, activeSheetId = null, activeSnapshotId = null, activePage = 'overview',
}) {
  const [open, setOpen] = useState(isOpen);
  const [expanded, setExpanded] = useState(false);
  const [presenterActive, setPresenterActive] = useState(false);
  const panel = useRef(null);
  const input = useRef(null);
  const returnFocus = useRef(null);
  const viewport = useChatViewport();
  const visible = open && !presenterActive;

  useEffect(() => setOpen(isOpen), [isOpen]);
  useEffect(() => {
    const listener = event => setPresenterActive(Boolean(event.detail));
    document.addEventListener('presentation-presenter', listener);
    return () => document.removeEventListener('presentation-presenter', listener);
  }, []);
  useEffect(() => {
    if (!visible) return;
    if (!panel.current?.contains(document.activeElement)) returnFocus.current = document.activeElement;
    const frame = requestAnimationFrame(() => input.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [visible, viewport.mobile]);
  useEffect(() => {
    if (!visible || !viewport.mobile) return;
    const root = document.getElementById('root');
    const priorInert = root?.inert;
    const priorOverflow = document.body.style.overflow;
    if (root) root.inert = true;
    document.body.style.overflow = 'hidden';
    return () => {
      if (root) root.inert = priorInert;
      document.body.style.overflow = priorOverflow;
    };
  }, [visible, viewport.mobile]);

  const show = () => { returnFocus.current = document.activeElement; setOpen(true); onToggle?.(true); };
  const close = () => {
    setOpen(false); onToggle?.(false); onClose?.();
    requestAnimationFrame(() => { if (returnFocus.current?.isConnected) returnFocus.current.focus(); });
  };
  const keyDown = event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    if (event.key !== 'Tab' || !viewport.mobile) return;
    const controls = [...panel.current.querySelectorAll('button:not([disabled]), textarea, a[href], [tabindex="0"]')]
      .filter(element => element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  if (presenterActive) return null;
  return createPortal(<>
    {!open && <button type="button" className="global-copilot-launcher hriday-launcher" onClick={show}
      aria-label="Open HRIDAY" aria-expanded={false} aria-controls="hriday-chat-panel">
      <span aria-hidden="true"><AnimatedAcousticOrb compact /></span><span>HRIDAY</span>
    </button>}
    {visible && <>
      {viewport.mobile && <div className="hriday-backdrop" aria-hidden="true" onClick={close} />}
      <section ref={panel} id="hriday-chat-panel" className={'hriday-panel' + (expanded ? ' hriday-panel--expanded' : '')}
        role="dialog" aria-label="HRIDAY" aria-modal={viewport.mobile || undefined} onKeyDown={keyDown}
        style={{ '--hriday-viewport-height': viewport.height + 'px', '--hriday-viewport-top': viewport.top + 'px' }}>
        <HRIDAYChat inputRef={input} mobile={viewport.mobile} expanded={expanded} onExpand={() => setExpanded(value => !value)}
          onClose={close} scope={() => hiddenChatScope({ activeDatasetId, activeSheetId, activeSnapshotId, activePage })} />
      </section>
    </>}
  </>, document.body);
}
