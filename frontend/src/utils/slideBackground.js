export function slideBackground(slide, color) {
  if (!slide.background_image) return { backgroundColor: color };
  const opacity = Math.max(0, Math.min(90, Number(slide.scrim_opacity ?? 70))) / 100;
  return {
    backgroundColor: color,
    backgroundImage: `linear-gradient(rgba(0,0,0,${opacity}), rgba(0,0,0,${opacity})), url(${JSON.stringify(slide.background_image)})`,
    backgroundSize: "cover", backgroundPosition: "center",
  };
}
