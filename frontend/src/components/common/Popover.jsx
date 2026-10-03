import React from "react";
import * as RadixPopover from "@radix-ui/react-popover";

export default function Popover({
  open,
  onOpenChange,
  trigger,
  children,
  contentClassName = "",
  align = "end",
  side = "bottom",
  sideOffset = 6,
  collisionPadding = 12,
  style,
  ...rest
}) {
  return (
    <RadixPopover.Root open={open} onOpenChange={onOpenChange} {...rest}>
      <RadixPopover.Trigger asChild>
        {trigger}
      </RadixPopover.Trigger>
      <RadixPopover.Portal>
        <RadixPopover.Content
          className={`radix-popover-content ${contentClassName}`.trim()}
          align={align}
          side={side}
          sideOffset={sideOffset}
          collisionPadding={collisionPadding}
          style={style}
        >
          {children}
        </RadixPopover.Content>
      </RadixPopover.Portal>
    </RadixPopover.Root>
  );
}
