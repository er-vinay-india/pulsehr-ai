import React from "react";
import ExecutiveVisualCard from "./ExecutiveVisualCard";

/**
 * ExecutiveVisualStory (Legacy wrapper): Re-exports ExecutiveVisualCard
 * ensuring zero regression for existing imports while adhering to new semantic DOM architecture.
 */
export default function ExecutiveVisualStory(props) {
  return <ExecutiveVisualCard {...props} />;
}
