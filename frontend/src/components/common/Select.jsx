import React, { useId } from "react";
import * as RadixSelect from "@radix-ui/react-select";
import { ChevronDown, Check } from "lucide-react";

const EMPTY_VALUE_SENTINEL = "__radix_empty__";

function toInternalValue(val) {
  if (val === "" || val === null || val === undefined) {
    return EMPTY_VALUE_SENTINEL;
  }
  return String(val);
}

function fromInternalValue(val) {
  if (val === EMPTY_VALUE_SENTINEL) {
    return "";
  }
  return val;
}

export default function Select({
  value,
  onValueChange,
  onChange,
  options,
  children,
  placeholder = "Select...",
  disabled = false,
  id,
  name,
  "aria-label": ariaLabel,
  className = "",
  triggerClassName = "",
  contentClassName = "",
  size = "md", // "sm" | "md" | "lg"
  fullWidth = false,
  icon = null,
  align = "start",
  side = "bottom",
  sideOffset = 4,
  title,
  style,
  triggerStyle,
  ...rest
}) {
  const generatedId = useId();
  const selectId = id || generatedId;

  // Extract options from options prop or children (<option>)
  const parsedOptions = React.useMemo(() => {
    if (Array.isArray(options) && options.length > 0) {
      return options.map((opt) => {
        if (typeof opt === "string" || typeof opt === "number") {
          return { value: String(opt), label: String(opt), disabled: false };
        }
        return {
          value: opt.value !== undefined ? String(opt.value) : "",
          label: opt.label !== undefined ? opt.label : String(opt.value),
          disabled: Boolean(opt.disabled),
          description: opt.description,
        };
      });
    }

    const extracted = [];
    React.Children.forEach(children, (child) => {
      if (!child) return;
      if (child.type === "option") {
        extracted.push({
          value: child.props.value !== undefined ? String(child.props.value) : "",
          label: child.props.children || child.props.value || "",
          disabled: Boolean(child.props.disabled),
        });
      } else if (child.props && child.props.value !== undefined) {
        extracted.push({
          value: String(child.props.value),
          label: child.props.children || child.props.label || String(child.props.value),
          disabled: Boolean(child.props.disabled),
        });
      }
    });
    return extracted;
  }, [options, children]);

  const handleValueChange = (newVal) => {
    const actualVal = fromInternalValue(newVal);
    if (onValueChange) {
      onValueChange(actualVal);
    }
    if (onChange) {
      onChange({
        target: { value: actualVal, name: selectId },
        currentTarget: { value: actualVal, name: selectId },
        value: actualVal,
        preventDefault: () => {},
        stopPropagation: () => {},
      });
    }
  };

  const internalValue = toInternalValue(value);

  // Find active option label for title tooltip if long text
  const currentOption = parsedOptions.find((o) => toInternalValue(o.value) === internalValue);
  const currentLabel = currentOption ? currentOption.label : "";
  const displayTitle = title || (typeof currentLabel === "string" ? currentLabel : undefined);

  const triggerClasses = [
    "radix-select-trigger",
    size && `radix-select-trigger--${size}`,
    fullWidth && "radix-select-trigger--full",
    triggerClassName,
    className,
  ].filter(Boolean).join(" ");

  return (
    <RadixSelect.Root
      value={internalValue}
      onValueChange={handleValueChange}
      disabled={disabled}
      {...rest}
    >
      <RadixSelect.Trigger
        id={selectId}
        name={name}
        className={triggerClasses}
        aria-label={ariaLabel}
        title={displayTitle}
        style={{ ...style, ...triggerStyle }}
      >
        {icon && (
          <span
            className="radix-select-leading-icon"
            style={{ display: "inline-flex", alignItems: "center", flexShrink: 0 }}
          >
            {icon}
          </span>
        )}
        <span className="radix-select-value">
          <RadixSelect.Value placeholder={placeholder} />
        </span>
        <RadixSelect.Icon className="radix-select-icon">
          <ChevronDown size={14} />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          className={`radix-select-content ${contentClassName}`.trim()}
          position="popper"
          side={side}
          sideOffset={sideOffset}
          align={align}
          collisionPadding={8}
        >
          <RadixSelect.Viewport className="radix-select-viewport">
            {parsedOptions.map((opt, idx) => (
              <RadixSelect.Item
                key={`${opt.value}-${idx}`}
                value={toInternalValue(opt.value)}
                disabled={opt.disabled}
                className="radix-select-item"
                title={typeof opt.label === "string" ? opt.label : undefined}
              >
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
                  <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                  {opt.description && (
                    <span className="radix-select-item-desc">{opt.description}</span>
                  )}
                </div>
                <RadixSelect.ItemIndicator className="radix-select-item-indicator">
                  <Check size={14} />
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
