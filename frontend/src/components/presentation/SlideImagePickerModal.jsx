import React, { useState, useEffect } from "react";
import { Search, Image, X, Check, Sliders, Sparkles, ExternalLink } from "lucide-react";

const CATEGORIES = [
  { id: "all", label: "All Curated" },
  { id: "executive", label: "Executive Board" },
  { id: "operations", label: "Frontline & Retail" },
  { id: "team", label: "Team Collaboration" },
  { id: "analytics", label: "Data & Finance" },
];

export default function SlideImagePickerModal({
  isOpen,
  onClose,
  onSelectImage,
  currentImageUrl = null,
}) {
  const [query, setQuery] = useState("workplace");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [scrimOpacity, setScrimOpacity] = useState(70); // 70% dark overlay for WCAG AAA text contrast

  // Fetch free images
  const fetchImages = async (searchQuery, category) => {
    setLoading(true);
    try {
      const catParam = category && category !== "all" ? `&category=${encodeURIComponent(category)}` : "";
      const qParam = encodeURIComponent(searchQuery || "workplace");
      const res = await fetch(`/api/presentations/images/search?query=${qParam}${catParam}&page_size=12`);
      if (res.ok) {
        const data = await res.json();
        setImages(data.images || []);
      }
    } catch (err) {
      console.error("Failed to fetch royalty-free images:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchImages(query, selectedCategory);
    }
  }, [isOpen, selectedCategory]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchImages(query, selectedCategory);
  };

  const handleApply = (applyToAll = false) => {
    if (!selectedImage) return;
    onSelectImage({
      url: selectedImage.url,
      thumbnail: selectedImage.thumbnail,
      title: selectedImage.title,
      creator: selectedImage.creator,
      scrimOpacity,
      applyToAll,
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="pres-image-picker-overlay" onClick={onClose}>
      <div className="pres-image-picker-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="pres-image-picker-header">
          <div className="header-left">
            <div className="header-icon">
              <Image size={18} />
            </div>
            <div>
              <h3 className="header-title">Royalty-Free Imagery Engine</h3>
              <p className="header-sub">
                Curated commercial-use enterprise photography with automatic dark contrast scrim.
              </p>
            </div>
          </div>
          <button type="button" className="btn-close" onClick={onClose} aria-label="Close image picker">
            <X size={18} />
          </button>
        </div>

        {/* Search & Categories */}
        <div className="pres-image-picker-controls">
          <form onSubmit={handleSearchSubmit} className="search-form">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search free images (e.g., retail store, boardroom meeting, analytics)..."
              className="search-input"
            />
            <button type="submit" className="btn-search">
              Search
            </button>
          </form>

          <div className="category-pills">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`cat-pill ${selectedCategory === cat.id ? "active" : ""}`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Scrim Contrast Control & Active Selection Preview */}
        <div className="scrim-control-bar">
          <div className="scrim-slider-group">
            <Sliders size={14} />
            <span className="scrim-label">Dark Scrim Contrast:</span>
            <input
              type="range"
              min="0"
              max="90"
              step="5"
              value={scrimOpacity}
              onChange={(e) => setScrimOpacity(Number(e.target.value))}
              className="scrim-slider"
            />
            <span className="scrim-value">{scrimOpacity}%</span>
            <span className="scrim-hint">(Ensures white text readability)</span>
          </div>

          {selectedImage && (
            <div className="selected-preview-pill">
              <span>Selected: <strong>{selectedImage.title}</strong></span>
            </div>
          )}
        </div>

        {/* Image Grid */}
        <div className="pres-image-grid">
          {loading ? (
            <div className="grid-loading">
              <Sparkles size={24} className="spin-icon" />
              <span>Fetching royalty-free commercial photography...</span>
            </div>
          ) : images.length === 0 ? (
            <div className="grid-empty">
              <p>No images found matching your search. Try &quot;office&quot;, &quot;team&quot;, or &quot;retail&quot;.</p>
            </div>
          ) : (
            images.map((img) => {
              const isSelected = selectedImage?.id === img.id || currentImageUrl === img.url;
              return (
                <div
                  key={img.id}
                  className={`image-card ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedImage(img)}
                >
                  <div className="image-wrapper">
                    <img src={img.thumbnail} alt={img.title} loading="lazy" />
                    {/* Simulated live scrim */}
                    <div
                      className="image-scrim-preview"
                      style={{ backgroundColor: `rgba(16, 14, 12, ${scrimOpacity / 100})` }}
                    />
                    {isSelected && (
                      <div className="selected-badge">
                        <Check size={16} />
                      </div>
                    )}
                  </div>
                  <div className="image-info">
                    <span className="image-title" title={img.title}>
                      {img.title}
                    </span>
                    <span className="image-creator">{img.creator} · {img.source}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Actions */}
        <div className="pres-image-picker-footer">
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cancel
          </button>
          <div className="apply-btn-group">
            <button
              type="button"
              className="btn-apply-all"
              disabled={!selectedImage}
              onClick={() => handleApply(true)}
              title="Apply this photographic background across all slides"
            >
              Apply to All Slides
            </button>
            <button
              type="button"
              className="btn-apply"
              disabled={!selectedImage}
              onClick={() => handleApply(false)}
            >
              Apply to Current Slide
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
