import React, { useId, useRef, useState, useEffect } from "react";
import DeckFloatingLayer from "./DeckFloatingLayer.jsx";

// Keep each control's layout wrapper while rendering its help outside the slide.
export default function DeckControl({ children, ...props }) {
  const anchorRef = useRef(null);
  const timer = useRef(null);
  const id = useId();
  const [open, setOpen] = useState(false);
  const items = React.Children.toArray(children);
  const tooltip = items.find(child => child.props?.className === "symbolic-tooltip");
  const cancelHide = () => clearTimeout(timer.current);
  const hide = () => { cancelHide(); timer.current = setTimeout(() => setOpen(false), 120); };
  useEffect(() => () => clearTimeout(timer.current), []);
  const describe = child => {
    if (!React.isValidElement(child)) return child;
    if (["button", "select"].includes(child.type)) {
      return React.cloneElement(child, { "aria-describedby": open ? [child.props["aria-describedby"], id].filter(Boolean).join(" ") : child.props["aria-describedby"] });
    }
    return child.props.children ? React.cloneElement(child, {}, React.Children.map(child.props.children, describe)) : child;
  };
  return (
    <div {...props} ref={anchorRef}
      onMouseEnter={() => { cancelHide(); setOpen(true); }} onMouseLeave={hide}
      onFocus={event => { if (event.target.matches(":focus-visible")) { cancelHide(); setOpen(true); } }}
      onBlur={hide}>
      {items.filter(child => child !== tooltip).map(describe)}
      {open && tooltip && <DeckFloatingLayer anchorRef={anchorRef} id={id} onClose={() => setOpen(false)}
        onMouseEnter={cancelHide} onMouseLeave={hide}>{tooltip.props.children}</DeckFloatingLayer>}
    </div>
  );
}
