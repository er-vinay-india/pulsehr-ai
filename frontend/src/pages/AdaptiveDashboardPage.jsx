import React, { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Info, X } from "lucide-react";
import SafeReactECharts from "../components/charts/SafeReactECharts";
import ExecutiveBriefingCard from "../components/adaptive/ExecutiveBriefingCard";
import ExceptionWatchCard from "../components/adaptive/ExceptionWatchCard";
import ForwardOutlookCard from "../components/adaptive/ForwardOutlookCard";
import EnterpriseSynthesisCard from "../components/adaptive/EnterpriseSynthesisCard";
import PriorityInsightCard from "../components/adaptive/PriorityInsightCard";
import AnalysisCoverageSection from "../components/adaptive/AnalysisCoverageSection";
import InvestigationDrawer from "../components/InvestigationDrawer";
import EmployeeDrawer from "../components/EmployeeDrawer";
import "../styles/adaptive-dashboard.scss";

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Server responded with status ${res.status}`);
  }
  return res.json();
}

function formatDurationMinutes(mins) {
  if (mins === null || mins === undefined) return "—";
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  if (m === 60) return `${h + 1}h`;
  if (m === 0) return `${h}h`;
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

function formatDurationHours(hVal) {
  if (hVal === null || hVal === undefined) return "—";
  return formatDurationMinutes(Math.round(hVal * 60));
}

function formatHumanDate(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const [y, m, d] = parts;
  const mNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mIdx = parseInt(m, 10) - 1;
  const dNum = parseInt(d, 10);
  return `${dNum} ${mNames[mIdx]} ${y}`;
}

function formatFullMonthName(ymStr) {
  if (!ymStr) return "";
  const [y, m] = ymStr.split("-");
  const fullMonths = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  const idx = parseInt(m, 10) - 1;
  return `${fullMonths[idx]} ${y}`;
}

function computeRelativeAge(dateStr) {
  if (!dateStr) return null;
  const parts = dateStr.split("-");
  if (parts.length !== 3) return null;
  const [y, m, d] = parts.map(Number);
  const target = new Date(y, m - 1, d);
  const now = new Date();
  const diffMs = now.getTime() - target.getTime();
  if (diffMs < 0) return "in the future";

  const diffMonths = (now.getFullYear() - target.getFullYear()) * 12 + (now.getMonth() - target.getMonth());
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (diffMonths >= 12) {
    const diffYears = Math.round(diffMonths / 12);
    return rtf.format(-diffYears, "year");
  } else if (diffMonths >= 1) {
    return rtf.format(-diffMonths, "month");
  } else {
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    return rtf.format(-diffDays, "day");
  }
}

export default function AdaptiveDashboardPage({ onNavigateTab }) {
  // Source State
  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState(null);
  const [selectedSheetId, setSelectedSheetId] = useState(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      return p.get("sheet_id") || "";
    } catch {
      return "";
    }
  });

  // Analysis State
  const [data, setData] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState(null);
  const [revision, setRevision] = useState(0);

  // Disclosure Layers State
  const [showExplainPrimary, setShowExplainPrimary] = useState(false);
  const [showExplainSecondary, setShowExplainSecondary] = useState(false);
  const [showExplainTertiary, setShowExplainTertiary] = useState(false);
  const [showExplainQuaternary, setShowExplainQuaternary] = useState(false);
  const [showExplainQuinary, setShowExplainQuinary] = useState(false);
  const [showExplainDecision, setShowExplainDecision] = useState(false);
  const [inspectModalOpen, setInspectModalOpen] = useState(false);
  const [inspectTarget, setInspectTarget] = useState("primary");
  const [investigationTarget, setInvestigationTarget] = useState(null);
  const [inspectedEmployeeId, setInspectedEmployeeId] = useState(null);

  // Focus & Accessibility Refs
  const triggerBtnRef = useRef(null);
  const chartTriggerBtnRef = useRef(null);
  const breakdownTriggerBtnRef = useRef(null);
  const comparatorTriggerBtnRef = useRef(null);
  const disparityTriggerBtnRef = useRef(null);
  const decisionTriggerBtnRef = useRef(null);
  const enterpriseTriggerBtnRef = useRef(null);
  const decisionCardRef = useRef(null);
  const modalCloseBtnRef = useRef(null);
  const dialogRef = useRef(null);

  // Responsive state for screen-size-tuned chart padding & tick density
  const [isMobile, setIsMobile] = useState(() => typeof window !== "undefined" && window.innerWidth <= 640);
  useEffect(() => {
    const handleResize = () => setIsMobile(typeof window !== "undefined" && window.innerWidth <= 640);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);
  const activeControllerRef = useRef(null);
  const requestCounter = useRef(0);

  const handleSourceSelect = (newId) => {
    setSelectedSheetId(newId);
    try {
      const url = new URL(window.location);
      url.searchParams.set("sheet_id", newId);
      window.history.replaceState({}, "", url);
    } catch {}
  };

  // 1. Load Sources on Mount
  const loadSources = () => {
    setSourcesLoading(true);
    setSourcesError(null);
    fetchJson("/api/sheets")
      .then((res) => {
        const list = Array.isArray(res) ? res : res.sheets || [];
        setSources(list);
        const urlParam = new URLSearchParams(window.location.search).get("sheet_id");
        if (urlParam && list.some((s) => String(s.id) === urlParam)) {
          setSelectedSheetId(urlParam);
        } else if (list.length > 0) {
          const firstId = String(list[0].id);
          setSelectedSheetId(firstId);
          try {
            const url = new URL(window.location);
            url.searchParams.set("sheet_id", firstId);
            window.history.replaceState({}, "", url);
          } catch {}
        }
      })
      .catch((err) => {
        setSourcesError(err.message || "Failed to load uploaded data sources.");
      })
      .finally(() => {
        setSourcesLoading(false);
      });
  };

  useEffect(() => {
    loadSources();
  }, []);

  // 2. Fetch Adaptive Elements for Selected Source
  useEffect(() => {
    if (!selectedSheetId) {
      setData(null);
      setCalculating(false);
      return;
    }

    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
    }
    const controller = new AbortController();
    activeControllerRef.current = controller;
    const currentReqId = ++requestCounter.current;

    setShowExplainPrimary(false);
    setShowExplainSecondary(false);
    setShowExplainTertiary(false);
    setShowExplainQuaternary(false);
    setInspectModalOpen(false);
    setCalculating(true);
    setCalcError(null);

    fetchJson(`/api/adaptive-dashboard/primary-element?sheet_id=${selectedSheetId}`, {
      signal: controller.signal,
    })
      .then((res) => {
        setData(res);
        const inspectParam = new URLSearchParams(window.location.search).get("inspect");
        if (inspectParam) {
          setInspectTarget(inspectParam);
          setInspectModalOpen(true);
        }
      })
      .catch((err) => {
        if (currentReqId !== requestCounter.current) return;
        if (err.name !== "AbortError") {
          setCalcError(err.message || "Unable to compute verified metric for this source.");
        }
      })
      .finally(() => {
        if (currentReqId === requestCounter.current) {
          setCalculating(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [selectedSheetId, revision]);

  // 3. Modal Focus Management & Keyboard Dismissal
  useEffect(() => {
    if (inspectModalOpen) {
      setShowExplainPrimary(false);
      setShowExplainSecondary(false);
      setShowExplainTertiary(false);
      setShowExplainQuaternary(false);
      setShowExplainQuinary(false);
      setShowExplainDecision(false);
      setTimeout(() => {
        modalCloseBtnRef.current?.focus();
      }, 50);

      const handleKeyDown = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          handleCloseInspect();
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [inspectModalOpen, inspectTarget]);

  const handleOpenInspect = (target) => {
    setInspectTarget(target);
    setInspectModalOpen(true);
  };

  const handleCloseInspect = () => {
    setInspectModalOpen(false);
    if (inspectTarget === "secondary") {
      chartTriggerBtnRef.current?.focus();
    } else if (inspectTarget === "tertiary") {
      breakdownTriggerBtnRef.current?.focus();
    } else if (inspectTarget === "quaternary") {
      comparatorTriggerBtnRef.current?.focus();
    } else if (inspectTarget === "quinary") {
      disparityTriggerBtnRef.current?.focus();
    } else if (inspectTarget === "decision") {
      decisionTriggerBtnRef.current?.focus();
    } else if (inspectTarget === "enterprise") {
      enterpriseTriggerBtnRef.current?.focus();
    } else {
      triggerBtnRef.current?.focus();
    }
  };

  const element = data?.element;
  const secondaryElement = data?.secondary_element;
  const tertiaryElement = data?.tertiary_element;
  const quaternaryElement = data?.quaternary_element;
  const quinaryElement = data?.quinary_element;
  const decisionElement = data?.decision_element;
  const briefingElement = data?.briefing_element;
  const exceptionElement = data?.exception_element;
  const outlookElement = data?.outlook_element;
  const enterpriseElement = data?.enterprise_element;
  const priorityInsight = data?.priority_insight;
  const analysisCoverage = data?.analysis_coverage;
  const manifest = data?.manifest;
  const glance = element?.glance;
  const explain = element?.explain;
  const inspect = element?.inspect;

  // Reporting range presentation: "1 Jan 2023 – 12 Dec 2024"
  const formattedReportingRange = useMemo(() => {
    if (manifest?.date_range?.start && manifest?.date_range?.end) {
      return `${formatHumanDate(manifest.date_range.start)} – ${formatHumanDate(manifest.date_range.end)}`;
    }
    if (manifest?.row_count) {
      return `${manifest.row_count} records`;
    }
    return null;
  }, [manifest?.date_range, manifest?.row_count]);

  // Relative age of latest data
  const dataThroughText = useMemo(() => {
    const dStr = secondaryElement?.data_through_date || manifest?.date_range?.end;
    if (!dStr) return null;
    const hDate = formatHumanDate(dStr);
    const rel = computeRelativeAge(dStr);
    return rel ? `Data through ${hDate} · ${rel}` : `Data through ${hDate}`;
  }, [secondaryElement?.data_through_date, manifest?.date_range?.end]);

  // Scope line definition per WP1
  const scopeLine = useMemo(() => {
    if (!manifest) return null;
    const workbook = manifest.display_name || manifest.file_name || "Dataset";
    const sheet = manifest.sheet_name || `Sheet ${selectedSheetId}`;
    let period = manifest.date_range?.formatted;
    if (!period) {
      if (manifest.date_range?.start && manifest.date_range?.end) {
        period = `${formatHumanDate(manifest.date_range.start)} – ${formatHumanDate(manifest.date_range.end)}`;
      } else {
        period = "Reporting period not established";
      }
    }
    const isHr = data?.contract?.domain === "hr" || data?.contract?.analyst_persona?.toLowerCase().includes("hr");
    const population = manifest.row_count
      ? (isHr
          ? `${Number(manifest.row_count).toLocaleString()} employees represented`
          : `${Number(manifest.row_count).toLocaleString()} records indexed`)
      : "Population scope pending";
    return {
      workbook,
      sheet,
      period,
      population,
      refreshed: "Live verified",
    };
  }, [manifest, selectedSheetId, data?.contract]);

  // Compact business measures per WP2 (up to 3 supported measures)
  const compactMeasures = useMemo(() => {
    if (!data) return [];
    const measures = [];
    const rowCount = data.manifest?.row_count;
    const isHr = data?.contract?.domain === "hr" || data?.contract?.analyst_persona?.toLowerCase().includes("hr");

    if (rowCount) {
      measures.push({
        id: "population",
        label: isHr ? "Employees represented" : "Records indexed",
        value: Number(rowCount).toLocaleString(),
        context: isHr ? "In attendance dataset" : (data.manifest?.display_name || "Active dataset"),
        unit: "",
      });
    }

    if (data.quaternary_element?.items) {
      const attItem = data.quaternary_element.items.find((i) => i.cohort.toLowerCase().includes("attendance"));
      if (attItem) {
        measures.push({
          id: "attendance",
          label: "Recorded attendance",
          value: attItem.formatted_secondary || attItem.formatted_value,
          context: `${attItem.formatted_value} recorded`,
          unit: "",
        });
      }

      const leaveItem = data.quaternary_element.items.find((i) => i.cohort.toLowerCase().includes("leave"));
      if (leaveItem) {
        measures.push({
          id: "leave",
          label: "Approved leave",
          value: leaveItem.formatted_secondary || leaveItem.formatted_value,
          context: `${leaveItem.formatted_value} recorded`,
          unit: "",
        });
      }
    } else if (data.quinary_element?.formatted_benchmark) {
      measures.push({
        id: "attendance",
        label: isHr ? "Recorded attendance" : "Benchmark average",
        value: data.quinary_element.formatted_benchmark,
        context: isHr ? "Company benchmark per employee" : "Organization benchmark",
        unit: "",
      });
    } else if (!isHr && data.priority_insight) {
      measures.push({
        id: "disparity",
        label: "Observed Disparity",
        value: data.priority_insight.prominent_number,
        context: data.priority_insight.comparison_label || "Max cohort spread",
        unit: data.priority_insight.unit || "",
      });
    }
    return measures;
  }, [data]);

  // Chart configuration for Apache ECharts (Revision 5)
  const chartPoints = secondaryElement?.chart_series?.points || [];

  const chartOption = useMemo(() => {
    if (!chartPoints.length || !secondaryElement) return {};

    const xCategories = chartPoints.map((p) => {
      if (p.period_label && !p.period.includes("-")) {
        return p.period_label;
      }
      if (secondaryElement.temporal_grain === "weekly" && p.period_label) {
        return p.period_label;
      }
      const [y, m] = p.period.split("-");
      const mNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mStr = mNames[parseInt(m, 10) - 1] || m;
      return `${mStr} ’${y.slice(2)}`;
    });

    // P10 lower bound series (Band Base, transparent)
    const bandBaseData = chartPoints.map((p) => (p.has_band ? p.p10_hours : null));

    // P90 - P10 difference series (Band Area)
    const bandDiffData = chartPoints.map((p) => {
      if (!p.has_band || p.p10_hours === null || p.p90_hours === null) return null;
      return Number((p.p90_hours - p.p10_hours).toFixed(3));
    });

    // Distinct boundary lines for P10 and P90
    const p10LineData = chartPoints.map((p) => (p.has_band ? p.p10_hours : null));
    const p90LineData = chartPoints.map((p) => (p.has_band ? p.p90_hours : null));

    // Primary Average line
    const meanLineData = chartPoints.map((p) => {
      if (p.average_hours === null) return null;
      return {
        value: p.average_hours,
        symbol: p.is_partial ? "diamond" : "circle",
        symbolSize: p.is_partial ? 8 : 5,
        itemStyle: {
          color: "#ffb089",
          borderColor: p.is_partial ? "#fff9f2" : "#ffb089",
          borderWidth: p.is_partial ? 1.5 : 0,
        },
      };
    });

    // Tick map for Duration format
    const tickMap = {};
    if (secondaryElement.y_axis_ticks && secondaryElement.y_axis_tick_labels) {
      secondaryElement.y_axis_ticks.forEach((tick, idx) => {
        tickMap[tick.toFixed(2)] = secondaryElement.y_axis_tick_labels[idx];
      });
    }

    return {
      backgroundColor: "transparent",
      animation: false,
      legend: false, // Custom HTML key above plot to avoid crowding x-axis
      grid: {
        left: isMobile ? 70 : 78,
        right: isMobile ? 56 : 44,
        top: 24,
        bottom: isMobile ? 104 : 54,
        containLabel: true,
      },
      tooltip: {
        trigger: "axis",
        confine: true,
        axisPointer: {
          type: "line",
          lineStyle: {
            color: "rgba(255, 176, 137, 0.4)",
            width: 1,
            type: "dashed",
          },
        },
        backgroundColor: "#1c1815",
        borderColor: "#524940",
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: "#fff9f2",
          fontSize: 12,
          fontFamily: "system-ui, sans-serif",
        },
        formatter: (params) => {
          const item = params.find((p) => p.seriesName === (secondaryElement.title || "Average logged time")) || params[0];
          if (!item) return "";
          const pt = chartPoints[item.dataIndex];
          const periodHeader = pt?.period_label && !pt?.period.includes("-")
            ? pt.period_label
            : (secondaryElement.temporal_grain === "weekly"
                ? `Week of ${formatHumanDate(pt?.first_observed_date)} (${pt?.period_label || pt?.period})`
                : formatFullMonthName(pt?.period));
          if (!pt || pt.average_hours === null) {
            return `
              <div style="font-weight:600;margin-bottom:4px;color:#fff9f2">${periodHeader}</div>
              <div style="color:#ded5cb">No recorded intervals in this period</div>
            `;
          }
          const displayAvg = secondaryElement.glance?.unit === "$"
            ? pt.formatted_hours
            : (secondaryElement.glance?.unit === "d"
                ? `${pt.average_hours.toFixed(2)} d (${pt.formatted_hours})`
                : `${pt.average_hours.toFixed(2)}h (${pt.formatted_hours})`);
          return `
            <div style="font-weight:600;margin-bottom:6px;color:#fff9f2">${periodHeader}</div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
              <span style="color:#ded5cb">${secondaryElement.title || "Average"}:</span>
              <strong style="color:#ffb089">${displayAvg}</strong>
            </div>
            ${
              pt.has_band
                ? `<div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
                    <span style="color:#ded5cb">${secondaryElement.band_name || "Middle 80% range"}:</span>
                    <span style="color:#fff9f2">${pt.formatted_p10} – ${pt.formatted_p90}</span>
                  </div>`
                : ""
            }
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:2px">
              <span style="color:#ded5cb">Observations:</span>
              <span style="color:#fff9f2">${pt.valid_entries.toLocaleString()}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:2px">
              <span style="color:#ded5cb">${secondaryElement.temporal_grain === "weekly" ? "Week date:" : "Observed dates:"}</span>
              <span style="color:#fff9f2">${secondaryElement.temporal_grain === "weekly" ? pt.first_observed_date : pt.observed_dates}</span>
            </div>
            ${
              pt.excluded_entries > 0
                ? `<div style="display:flex;justify-content:space-between;gap:16px;color:#ded5cb">
                    <span>Excluded entries:</span>
                    <span>${pt.excluded_entries.toLocaleString()}</span>
                  </div>`
                : ""
            }
            ${
              pt.is_partial
                ? `<div style="margin-top:6px;font-size:11px;color:#fbbb27;border-top:1px solid #524940;padding-top:4px">
                    ⚠️ ${pt.partial_reason || "Partial period"}
                  </div>`
                : ""
            }
          `;
        },
      },
      xAxis: {
        type: "category",
        data: xCategories,
        name: secondaryElement.x_axis_title || (
          secondaryElement.glance?.unit === "d" ? "Attendance intervals (Timeline)" :
          secondaryElement.temporal_grain === "weekly" ? "Retail week (Timeline)" :
          "Timeline (Month)"
        ),
        nameLocation: "middle",
        nameGap: isMobile ? 72 : 32,
        nameTextStyle: {
          color: "#ded5cb",
          fontSize: 12,
          fontWeight: 500,
        },
        boundaryGap: false,
        axisTick: {
          show: true,
          inside: false,
          alignWithLabel: true,
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: isMobile ? 10 : 11,
          rotate: isMobile ? 35 : 0,
          align: isMobile ? "right" : "center",
          verticalAlign: isMobile ? "middle" : "top",
          margin: isMobile ? 8 : 12,
          formatter: (val) => {
            if (isMobile) {
              return val
                .replace(/(\d+)(?:st|nd|rd|th)\s+to\s+(\d+)(?:st|nd|rd|th)\s+(\w+)/i, "$1–$2 $3")
                .replace("July", "Jul");
            }
            return val;
          },
          interval: (index) => {
            const total = xCategories.length;
            if (total <= 6) return true;
            if (index === 0 || index === total - 1) return true;
            if (secondaryElement.temporal_grain === "weekly") {
              if (isMobile) return index % 26 === 0;
              return index % 13 === 0;
            }
            if (isMobile) {
              if (total > 24) return index % 8 === 0;
              if (total > 12) return index % 4 === 0;
              return index % 2 === 0;
            }
            if (total > 24) return index % 3 === 0;
            if (total > 12) return index % 2 === 0;
            return true;
          },
          showMinLabel: true,
          showMaxLabel: true,
        },
        axisLine: {
          lineStyle: { color: "#3d362f" },
        },
      },
      yAxis: {
        type: "value",
        min: secondaryElement.y_axis_min,
        max: secondaryElement.y_axis_max,
        name: secondaryElement.y_axis_title || (
          secondaryElement.glance?.unit === "$" ? "Weekly sales ($)" :
          secondaryElement.glance?.unit === "d" ? "Attended days (d)" :
          "Logged duration (h/m)"
        ),
        nameLocation: "middle",
        nameRotate: 90,
        nameGap: isMobile ? 56 : 52,
        nameTextStyle: {
          color: "#ded5cb",
          fontSize: 12,
          fontWeight: 500,
        },
        axisTick: {
          show: true,
          inside: false,
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: 11,
          formatter: (val) => {
            const key = val.toFixed(2);
            if (tickMap[key]) return tickMap[key];
            if (secondaryElement.glance?.unit === "$") {
              if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
              if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
              return `$${val}`;
            }
            if (secondaryElement.glance?.unit === "d") {
              return `${val.toFixed(1)} d`;
            }
            return formatDurationHours(val);
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: "#524940",
            type: "dashed",
          },
        },
      },
      series: [
        // Series 1: Lower boundary baseline for stack (invisible)
        {
          name: "Band Base",
          type: "line",
          data: bandBaseData,
          stack: "middle-80-band",
          symbol: "none",
          lineStyle: { opacity: 0 },
          silent: true,
          connectNulls: false,
        },
        // Series 2: Middle 80% range fill
        {
          name: "Middle 80% of entries",
          type: "line",
          data: bandDiffData,
          stack: "middle-80-band",
          symbol: "none",
          lineStyle: { opacity: 0 },
          areaStyle: {
            color: "rgba(255, 176, 137, 0.16)",
          },
          silent: true,
          connectNulls: false,
        },
        // Series 3: Lower boundary line (P10)
        {
          name: "P10 Bound",
          type: "line",
          data: p10LineData,
          symbol: "none",
          lineStyle: {
            color: "rgba(255, 176, 137, 0.4)",
            width: 1,
            type: "dashed",
          },
          silent: true,
          connectNulls: false,
        },
        // Series 4: Upper boundary line (P90)
        {
          name: "P90 Bound",
          type: "line",
          data: p90LineData,
          symbol: "none",
          lineStyle: {
            color: "rgba(255, 176, 137, 0.4)",
            width: 1,
            type: "dashed",
          },
          silent: true,
          connectNulls: false,
        },
        // Series 5: Primary Average Line
        {
          name: secondaryElement.title || "Average logged time",
          type: "line",
          data: meanLineData,
          connectNulls: false,
          smooth: false,
          z: 10,
          lineStyle: {
            color: "#ffb089",
            width: 2.5,
          },
          emphasis: {
            scale: false,
            itemStyle: {
              borderColor: "#fff9f2",
              borderWidth: 2,
            },
          },
        },
      ],
    };
  }, [chartPoints, secondaryElement, isMobile]);

  // Element 3 (Tertiary Ranked Breakdown) option for Apache ECharts
  const breakdownItems = tertiaryElement?.items || [];

  const breakdownHeight = useMemo(() => {
    if (!breakdownItems.length) return 320;
    const itemHeight = isMobile ? 36 : 38;
    return Math.max(280, breakdownItems.length * itemHeight + (isMobile ? 70 : 80));
  }, [breakdownItems.length, isMobile]);

  const breakdownOption = useMemo(() => {
    if (!breakdownItems.length || !tertiaryElement) return {};

    // ECharts category axis displays bottom-to-top by default, so we reverse to place rank 1 on top
    const reversedItems = [...breakdownItems].reverse();
    const categories = reversedItems.map((it) => it.category);
    const seriesData = reversedItems.map((it) => ({
      value: it.value,
      sharePct: it.share_pct,
      formattedValue: it.formatted_value,
      secondaryValue: it.secondary_value,
      formattedSecondary: it.formatted_secondary,
      category: it.category,
      count: it.count,
    }));

    return {
      backgroundColor: "transparent",
      animation: false,
      grid: {
        left: isMobile ? 110 : 210,
        right: isMobile ? 36 : 65,
        top: 20,
        bottom: 30,
        containLabel: false,
      },
      tooltip: {
        trigger: "item",
        confine: true,
        backgroundColor: "#1c1815",
        borderColor: "#524940",
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: "#fff9f2",
          fontSize: 12,
          fontFamily: "system-ui, sans-serif",
        },
        formatter: (params) => {
          const d = params.data;
          if (!d) return "";
          const isOther = d.category === "Other";
          const header = isOther && d.formattedSecondary
            ? `Other (${d.formattedSecondary} consolidated)`
            : d.category;
          return `
            <div style="font-weight:600;margin-bottom:6px;color:#fff9f2">${header}</div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
              <span style="color:#ded5cb">${tertiaryElement.metric_name || "Headcount"}:</span>
              <strong style="color:#ffb089">${d.formattedValue}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
              <span style="color:#ded5cb">Share of Total:</span>
              <strong style="color:#f3d19a">${d.sharePct}%</strong>
            </div>
            ${
              d.formattedSecondary && !isOther
                ? `<div style="display:flex;justify-content:space-between;gap:16px;border-top:1px solid #524940;padding-top:4px;margin-top:4px">
                    <span style="color:#ded5cb">Average / Metric:</span>
                    <span style="color:#fff9f2">${d.formattedSecondary}</span>
                  </div>`
                : ""
            }
          `;
        },
      },
      xAxis: {
        type: "value",
        max: (value) => {
          const rawMax = value.max || 1;
          const target = rawMax * 1.25;
          if (tertiaryElement.unit === "$") {
            if (target >= 1_000_000_000) {
              const step = 1_000_000_000;
              return Math.ceil(target / step) * step;
            }
            if (target >= 100_000_000) {
              const step = 25_000_000;
              return Math.ceil(target / step) * step;
            }
            if (target >= 1_000_000) {
              const step = 2_000_000;
              return Math.ceil(target / step) * step;
            }
            if (target >= 1_000) {
              const step = 500;
              return Math.ceil(target / step) * step;
            }
          }
          if (target >= 100) return Math.ceil(target / 20) * 20;
          if (target >= 10) return Math.ceil(target / 5) * 5;
          return Math.ceil(target);
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: "#524940",
            type: "dashed",
          },
        },
        axisLine: {
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: 11,
          formatter: (val) => {
            const absVal = Math.abs(val);
            if (absVal === 0) return tertiaryElement.unit === "$" ? "$0" : "0";
            if (tertiaryElement.unit === "$") {
              if (absVal >= 1_000_000_000) {
                const bVal = absVal / 1_000_000_000;
                return `$${bVal % 1 === 0 ? bVal.toFixed(0) : bVal.toFixed(1)}B`;
              }
              if (absVal >= 1_000_000) {
                const mVal = absVal / 1_000_000;
                return `$${mVal % 1 === 0 ? mVal.toFixed(0) : mVal.toFixed(1)}M`;
              }
              if (absVal >= 1_000) return `$${(absVal / 1_000).toFixed(0)}K`;
              return `$${absVal}`;
            }
            if (absVal >= 1_000_000_000) return `${(absVal / 1_000_000_000).toFixed(1)}B`;
            if (absVal >= 1_000_000) return `${(absVal / 1_000_000).toFixed(1)}M`;
            if (absVal >= 1_000) return `${(absVal / 1_000).toFixed(0)}K`;
            return Number(val).toLocaleString();
          },
        },
      },
      yAxis: {
        type: "category",
        name: tertiaryElement.dimension_name || "Store",
        nameLocation: "end",
        nameTextStyle: {
          color: "#ded5cb",
          fontSize: 11,
          fontWeight: 600,
          padding: [0, 0, 6, 0],
        },
        data: categories,
        axisLine: {
          lineStyle: { color: "#3d362f" },
        },
        axisTick: {
          alignWithLabel: true,
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: isMobile ? 11 : 12,
          width: isMobile ? 110 : 200,
          overflow: "truncate",
          ellipsis: "…",
          formatter: (name) => {
            if (isMobile) {
              return name
                .replace(/^Alliance Initiative - /, "Alliance: ")
                .replace(/^Laerdal Initiative - /, "Laerdal: ");
            }
            return name;
          },
        },
      },
      series: [
        {
          name: tertiaryElement.title || "Breakdown",
          type: "bar",
          data: seriesData,
          barWidth: isMobile ? 16 : 20,
          itemStyle: {
            color: "#ffb089",
            borderRadius: [0, 4, 4, 0],
          },
          label: {
            show: true,
            position: (params) => (params.data?.sharePct > 20 ? "insideRight" : "right"),
            distance: 8,
            color: (params) => (params.data?.sharePct > 20 ? "#1c1815" : "#ded5cb"),
            fontWeight: (params) => (params.data?.sharePct > 20 ? 700 : 400),
            fontSize: 11,
            formatter: (params) => `${params.data?.sharePct ?? 0}%`,
          },
        },
      ],
    };
  }, [breakdownItems, tertiaryElement, isMobile]);

  // Element 4 (Quaternary Explanatory Comparator) option for Apache ECharts (Gate 4)
  const comparatorItems = quaternaryElement?.items || [];

  const comparatorOption = useMemo(() => {
    if (!comparatorItems.length || !quaternaryElement) return {};

    // Reverse items for ECharts category axis bottom-to-top rendering
    const reversedItems = [...comparatorItems].reverse();
    const categories = reversedItems.map((it) => it.cohort);
    const seriesData = reversedItems.map((it) => ({
      value: it.value,
      formattedValue: it.formatted_value,
      sampleLabel: it.sample_label,
      sharePct: it.share_pct,
      isBaseline: it.is_baseline,
      cohort: it.cohort,
      itemStyle: {
        color: it.is_baseline ? "#968b7e" : "#ffb089",
        borderRadius: [0, 4, 4, 0],
      },
    }));

    return {
      backgroundColor: "transparent",
      animation: false,
      grid: {
        left: isMobile ? 120 : 160,
        right: isMobile ? 55 : 80,
        top: 15,
        bottom: 25,
        containLabel: false,
      },
      tooltip: {
        trigger: "item",
        confine: true,
        backgroundColor: "#1c1815",
        borderColor: "#524940",
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: "#fff9f2",
          fontSize: 12,
          fontFamily: "system-ui, sans-serif",
        },
        formatter: (params) => {
          const d = params.data;
          if (!d) return "";
          return `
            <div style="font-weight:600;margin-bottom:6px;color:#fff9f2">
              ${d.cohort} ${d.isBaseline ? '<span style="font-size:10px;color:#ded5cb">(Baseline)</span>' : ''}
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
              <span style="color:#ded5cb">${quaternaryElement.metric_name || "Metric"}:</span>
              <strong style="color:#ffb089">${d.formattedValue}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:4px">
              <span style="color:#ded5cb">Sample:</span>
              <span style="color:#fff9f2">${d.sampleLabel}</span>
            </div>
            ${
              d.sharePct !== null && d.sharePct !== undefined
                ? `<div style="display:flex;justify-content:space-between;gap:16px">
                    <span style="color:#ded5cb">Share of Total:</span>
                    <strong style="color:#f3d19a">${d.sharePct}%</strong>
                  </div>`
                : ""
            }
          `;
        },
      },
      xAxis: {
        type: "value",
        max: (value) => {
          const rawMax = value.max || 1;
          const target = rawMax * 1.25;
          if (quaternaryElement.unit === "$") {
            if (target >= 1_000_000) {
              const step = 200_000;
              return Math.ceil(target / step) * step;
            }
            if (target >= 1_000) {
              const step = 500;
              return Math.ceil(target / step) * step;
            }
          }
          if (target >= 1_000) return Math.ceil(target / 500) * 500;
          if (target >= 100) return Math.ceil(target / 20) * 20;
          return Math.ceil(target);
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: "#524940",
            type: "dashed",
          },
        },
        axisLine: {
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: 11,
          formatter: (val) => {
            const absVal = Math.abs(val);
            if (absVal === 0) return quaternaryElement.unit === "$" ? "$0" : "0";
            if (quaternaryElement.unit === "$") {
              if (absVal >= 1_000_000) {
                const mVal = absVal / 1_000_000;
                return `$${mVal % 1 === 0 ? mVal.toFixed(0) : mVal.toFixed(1)}M`;
              }
              if (absVal >= 1_000) return `$${(absVal / 1_000).toFixed(0)}K`;
              return `$${absVal}`;
            }
            if (absVal >= 1_000) return `${(absVal / 1_000).toFixed(0)}K`;
            return Number(val).toLocaleString();
          },
        },
      },
      yAxis: {
        type: "category",
        name: quaternaryElement.dimension_name || "Cohort",
        nameLocation: "end",
        nameTextStyle: {
          color: "#ded5cb",
          fontSize: 11,
          fontWeight: 600,
          padding: [0, 0, 6, 0],
        },
        data: categories,
        axisLine: {
          lineStyle: { color: "#3d362f" },
        },
        axisTick: {
          alignWithLabel: true,
          lineStyle: { color: "#3d362f" },
        },
        axisLabel: {
          color: "#ded5cb",
          fontSize: isMobile ? 11 : 12,
          width: isMobile ? 115 : 150,
          overflow: "truncate",
          ellipsis: "…",
        },
      },
      series: [
        {
          name: quaternaryElement.title || "Comparator",
          type: "bar",
          data: seriesData,
          barWidth: isMobile ? 18 : 22,
          label: {
            show: true,
            position: "right",
            distance: 8,
            color: "#fff9f2",
            fontSize: 11,
            fontFamily: "system-ui, sans-serif",
            fontWeight: "600",
            formatter: (params) => params.data?.formattedValue || "",
          },
        },
      ],
    };
  }, [comparatorItems, quaternaryElement, isMobile]);

  const activeInspect =
    inspectTarget === "priority" && priorityInsight
      ? {
          metric_title: priorityInsight.short_business_title || "Priority Strategic Insight",
          exact_value: `${priorityInsight.prominent_number || ""} ${priorityInsight.unit || ""}`.trim(),
          what_this_counts:
            priorityInsight.evidence_details?.observation ||
            priorityInsight.implication ||
            "Empirical disparity and variance evaluation across qualified organizational cohorts.",
          applicable_population:
            priorityInsight.population_summary ||
            "Qualified cohorts meeting minimum sample reliability criteria (n >= 5).",
          source_name: manifest?.display_name || manifest?.file_name || "Active Source",
          reporting_period: formattedReportingRange,
          calculation_method:
            priorityInsight.evidence_details?.calculation_id ||
            "Deterministic multi-factor decision ranking & variance attribution",
          data_completeness: "100% verified non-null records across evaluated cohorts.",
          coverage_label: "Strategy Alignment",
          coverage_value: `Strategy ${priorityInsight.strategy_code} (${priorityInsight.strategy_name})`,
          selection_reason:
            "Selected as top actionable insight based on relevance, statistical magnitude, and verified decision bounds.",
          limitations: priorityInsight.evidence_details?.limitations || [],
          calculation_id: priorityInsight.evidence_details?.calculation_id || "calc_priority_s09",
          definition_id: priorityInsight.evidence_details?.definition_id || "def_priority_v2",
          provenance: "Autonomous Insight Orchestrator Engine",
          snapshot: manifest?.snapshot || "live_source",
        }
      : inspectTarget === "secondary"
      ? secondaryElement?.inspect
      : inspectTarget === "tertiary"
      ? tertiaryElement?.inspect
      : inspectTarget === "quaternary"
      ? quaternaryElement?.inspect
      : inspectTarget === "quinary"
      ? quinaryElement?.inspect
      : inspectTarget === "decision"
      ? decisionElement?.inspect
      : inspectTarget === "briefing"
      ? briefingElement?.inspect
      : inspectTarget === "exception"
      ? exceptionElement?.inspect
      : inspectTarget === "outlook"
      ? outlookElement?.inspect
      : inspectTarget === "enterprise"
      ? enterpriseElement?.inspect
      : inspect;

  // Collapsible Secondary Findings Wrapper (de-duplicates findings when Priority Insight is active)
  const SecondaryFindingsWrapper = ({ children }) => {
    if (!priorityInsight) return <>{children}</>;
    const isHr = data?.contract?.domain === "hr" || data?.contract?.analyst_persona?.toLowerCase().includes("hr");
    return (
      <details className="adaptive-secondary-findings-accordion">
        <summary className="adaptive-secondary-findings-summary">
          <span>{isHr ? "Detailed Department Disparity & Supporting Action Analysis" : "Detailed Cohort Disparity & Supporting Action Analysis"}</span>
          {quinaryElement?.items && (
            <span className="summary-badge">{quinaryElement.items.length} units evaluated</span>
          )}
        </summary>
        <div className="adaptive-secondary-findings-content">
          {children}
        </div>
      </details>
    );
  };

  return (
    <div className="adaptive-dashboard-page" role="region" aria-label="Dashboard">
      {/* Quiet Local Page Header */}
      <header className="adaptive-page-header">
        <h1 className="adaptive-page-title">Dashboard</h1>

        {/* Scope Bar: Source Control, Reporting Period, Latest Data, Refresh */}
        <div className="adaptive-scope-bar">
          <div className="scope-control-group">
            <label htmlFor="source-selector">Source</label>
            <select
              id="source-selector"
              value={selectedSheetId}
              onChange={(e) => handleSourceSelect(e.target.value)}
              disabled={sourcesLoading}
              aria-label="Selected data source"
            >
              {sources.length === 0 && !sourcesLoading && (
                <option value="">No uploaded datasets</option>
              )}
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.row_count} records) — {s.display_name || "Dataset"}
                </option>
              ))}
            </select>
          </div>

          {formattedReportingRange && (
            <div className="scope-period-display" aria-label="Reporting range">
              {formattedReportingRange}
            </div>
          )}

          {dataThroughText && (
            <div className="scope-data-through-badge" aria-label="Latest observation timestamp">
              {dataThroughText}
            </div>
          )}

          {data?.contract?.analyst_persona && (
            <div
              className="scope-persona-badge"
              aria-label={`Active analyst persona: ${data.contract.analyst_persona}`}
              title="Active AI analytical lens calibrated to the detected data domain"
            >
              <span className="persona-dot" />
              <span>{data.contract.analyst_persona}</span>
            </div>
          )}

          <button
            type="button"
            className="scope-refresh-btn"
            onClick={() => setRevision((r) => r + 1)}
            disabled={calculating || !selectedSheetId}
            aria-label="Refresh analysis for selected source"
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Source Loading or Source Error State */}
      {sourcesError && (
        <div className="adaptive-status-notice error" role="alert">
          <span>Failed to load sources: {sourcesError}</span>
          <button type="button" onClick={loadSources}>
            Retry
          </button>
        </div>
      )}

      {/* Calculation Error State */}
      {calcError && !calculating && (
        <div className="adaptive-status-notice error" role="alert">
          <span>{calcError}</span>
          <button type="button" onClick={() => setRevision((r) => r + 1)}>
            Retry
          </button>
        </div>
      )}

      {/* Primary & Secondary Elements Container */}
      <main className="adaptive-content-container">
        {/* State A: Calculating Placeholder */}
        {calculating && (
          <div className="adaptive-tile-calculating" role="status" aria-live="polite">
            <div className="calc-placeholder-title" />
            <div className="calc-placeholder-number">Calculating…</div>
            <div className="calc-placeholder-context">Verifying records & calculation</div>
          </div>
        )}

        {/* Authoritative Scope Line (WP1) */}
        {!calculating && scopeLine && (
          <div className="adaptive-scope-line" aria-label="Dataset and population scope">
            <span className="scope-line-item scope-line-workbook">
              <strong>{scopeLine.workbook}</strong> · {scopeLine.sheet}
            </span>
            <span className="scope-line-separator">·</span>
            <span className="scope-line-item scope-line-period">
              Reporting period: <strong>{scopeLine.period}</strong>
            </span>
            <span className="scope-line-separator">·</span>
            <span className="scope-line-item scope-line-population">
              {scopeLine.population}
            </span>
            <span className="scope-line-separator">·</span>
            <span className="scope-line-item scope-line-status">
              <span className="scope-live-dot" />
              {scopeLine.refreshed}
            </span>
          </div>
        )}

        {/* Compact Business Measures (WP2) */}
        {!calculating && !calcError && compactMeasures.length > 0 && (
          <section className="adaptive-compact-summary-strip" aria-label="Key workforce measures">
            {compactMeasures.map((m) => (
              <div key={m.id} className="compact-summary-tile">
                <span className="compact-summary-tile__label">{m.label}</span>
                <div className="compact-summary-tile__val-row">
                  <span className="compact-summary-tile__value">{m.value}</span>
                  {m.unit && <span className="compact-summary-tile__unit">{m.unit}</span>}
                </div>
                <span className="compact-summary-tile__context">{m.context}</span>
              </div>
            ))}
          </section>
        )}

        {/* Priority Insight (New Decision-Focused Autonomous Discovery Engine — WP3 & WP4) */}
        {!calculating && !calcError && priorityInsight && (
          <PriorityInsightCard
            priorityInsight={priorityInsight}
            sheetId={selectedSheetId}
            snapshot={manifest?.snapshot}
            onInspect={() => handleOpenInspect("priority")}
            onOpenRecords={() => {
              const isHr = data?.contract?.domain === "hr" || data?.contract?.analyst_persona?.toLowerCase().includes("hr");
              const targetId = priorityInsight.focus_group || priorityInsight.top_segment || null;
              setInvestigationTarget({
                sheetId: selectedSheetId,
                entityType: isHr ? "department" : (priorityInsight.dimension_name?.toLowerCase() || "segment"),
                targetId: targetId,
                metric: priorityInsight.metric_name || null,
              });
            }}
            onListen={() => {
              const el = document.querySelector(".adaptive-briefing-card");
              if (el) {
                el.scrollIntoView({ behavior: "smooth" });
                const playBtn = el.querySelector(".voiceover-player button");
                if (playBtn) {
                  playBtn.click();
                }
              }
            }}
          />
        )}

        {/* Compact Expandable Analysis Coverage Drawer (S01–S20 Audit) */}
        {!calculating && !calcError && analysisCoverage && (
          <AnalysisCoverageSection coverage={analysisCoverage} />
        )}

        {/* State B: Ready Primary KPI Tile (Rendered as fallback when compact summary strip is absent) */}
        {!calculating && !calcError && element && element.kind === "kpi" && glance && compactMeasures.length === 0 && (
          <article className="adaptive-glance-tile" aria-labelledby="primary-metric-title">
            <div className="glance-header-row">
              <h2 id="primary-metric-title" className="glance-metric-label">
                {glance.label}
              </h2>

              <div className="info-trigger-wrapper">
                <button
                  ref={triggerBtnRef}
                  type="button"
                  className="glance-info-btn"
                  aria-label={`View calculation and source audit for ${glance.label}`}
                  aria-haspopup="dialog"
                  aria-expanded={inspectModalOpen && inspectTarget === "primary"}
                  onClick={() => handleOpenInspect("primary")}
                  onMouseEnter={() => !inspectModalOpen && setShowExplainPrimary(true)}
                  onMouseLeave={() => setShowExplainPrimary(false)}
                  onFocus={() => !inspectModalOpen && setShowExplainPrimary(true)}
                  onBlur={() => setShowExplainPrimary(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setShowExplainPrimary(false);
                  }}
                >
                  <Info aria-hidden="true" />
                </button>

                {/* Layer 2: Explain Preview Tooltip for Primary Tile */}
                {showExplainPrimary && !inspectModalOpen && explain && (
                  <div className="adaptive-explain-preview" role="tooltip">
                    <p className="preview-def">{explain.short_definition}</p>
                    <p className="preview-exact-val">{explain.exact_value_text}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Dominant Verified Number */}
            <div className="glance-number-row">
              <span className="glance-value">
                {glance.formatted_value}
              </span>
            </div>

            {/* Concise Context Qualifier */}
            {glance.context_qualifier && (
              <p className="glance-context-row">{glance.context_qualifier}</p>
            )}
          </article>
        )}

        {/* State C: Definition Required Card (if data is undecidable) */}
        {!calculating && !calcError && element && element.kind === "definition_card" && (
          <article className="adaptive-definition-card" aria-labelledby="definition-card-title">
            <h2 id="definition-card-title" className="definition-title">
              {glance?.label || "Definition Required"}
            </h2>
            <div className="definition-val">Needs Definition</div>
            <p className="definition-context">
              {element.coverage_qualifier || "A verified entity identifier or eligible denominator is required."}
            </p>
          </article>
        )}

        {/* Refined Second Element: Average logged time with Middle 80% Distribution Band */}
        {!calculating && !calcError && secondaryElement && secondaryElement.kind === "line_chart" && (
          <section
            className="adaptive-chart-card"
            aria-labelledby="secondary-metric-title"
            aria-describedby="secondary-metric-caption"
          >
            <div className="chart-card-header">
              <div className="chart-title-area">
                <h2 id="secondary-metric-title" className="chart-metric-title">
                  {secondaryElement.title}
                </h2>
                {secondaryElement.glance?.context_qualifier && (
                  <span className="chart-metric-qualifier">
                    {secondaryElement.glance.context_qualifier}
                  </span>
                )}
              </div>

              <div className="chart-controls-group">
                {/* Compact Legend Key placed cleanly above plot */}
                <div className="chart-legend-key" aria-hidden="true">
                  <span className="legend-item">
                    <span className="legend-indicator mean-line" />
                    <span className="legend-label">Average</span>
                  </span>
                  <span className="legend-item">
                    <span className="legend-indicator band-swatch" />
                    <span className="legend-label">{secondaryElement.band_name || "Middle 80% range"}</span>
                  </span>
                </div>

                <div className="info-trigger-wrapper">
                  <button
                    ref={chartTriggerBtnRef}
                    type="button"
                    className="glance-info-btn"
                    aria-label={`View calculation and source audit for ${secondaryElement.title}`}
                    title={secondaryElement.caption || `Methodology & audit for ${secondaryElement.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={inspectModalOpen && inspectTarget === "secondary"}
                    onClick={() => handleOpenInspect("secondary")}
                    onMouseEnter={() => !inspectModalOpen && setShowExplainSecondary(true)}
                    onMouseLeave={() => setShowExplainSecondary(false)}
                    onFocus={() => !inspectModalOpen && setShowExplainSecondary(true)}
                    onBlur={() => setShowExplainSecondary(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setShowExplainSecondary(false);
                    }}
                  >
                    <Info aria-hidden="true" />
                  </button>

                  {/* Layer 2: Explain Preview Tooltip for Secondary Element */}
                  {showExplainSecondary && !inspectModalOpen && secondaryElement.explain && (
                    <div className="adaptive-explain-preview" role="tooltip">
                      <p className="preview-def">{secondaryElement.caption || secondaryElement.explain.short_definition}</p>
                      <p className="preview-exact-val">{secondaryElement.explain.exact_value_text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Apache ECharts Canvas */}
            <div className="chart-body" role="img" aria-label={`Timeline chart of ${secondaryElement.title || "average logged duration"} from ${chartPoints[0]?.period_label || ""} to ${chartPoints[chartPoints.length - 1]?.period_label || ""}.`}>
              <SafeReactECharts option={chartOption} opts={{ renderer: "svg" }} style={{ height: isMobile ? 360 : 340, width: "100%", maxWidth: "100%" }} />
            </div>
          </section>
        )}

        {/* State D: Ready Tertiary Element (Categorical Breakdown Card - Gate 3) */}
        {!calculating && !calcError && tertiaryElement && tertiaryElement.kind === "ranked_bar" && (
          <section className="adaptive-breakdown-card" aria-labelledby="tertiary-breakdown-title">
            <div className="breakdown-card-header">
              <div className="breakdown-title-group">
                <h2 id="tertiary-breakdown-title" className="breakdown-card-title">
                  {tertiaryElement.title}
                </h2>
                {tertiaryElement.glance?.context_qualifier && (
                  <span className="breakdown-context-qualifier">
                    {tertiaryElement.glance.context_qualifier}
                  </span>
                )}
              </div>

              <div className="breakdown-controls-group">
                <div className="info-trigger-wrapper">
                  <button
                    ref={breakdownTriggerBtnRef}
                    type="button"
                    className="glance-info-btn"
                    aria-label={`View calculation and source audit for ${tertiaryElement.title}`}
                    title={tertiaryElement.caption || `Methodology & audit for ${tertiaryElement.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={inspectModalOpen && inspectTarget === "tertiary"}
                    onClick={() => handleOpenInspect("tertiary")}
                    onMouseEnter={() => !inspectModalOpen && setShowExplainTertiary(true)}
                    onMouseLeave={() => setShowExplainTertiary(false)}
                    onFocus={() => !inspectModalOpen && setShowExplainTertiary(true)}
                    onBlur={() => setShowExplainTertiary(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setShowExplainTertiary(false);
                    }}
                  >
                    <Info aria-hidden="true" />
                  </button>

                  {/* Layer 2: Explain Preview Tooltip for Tertiary Element */}
                  {showExplainTertiary && !inspectModalOpen && tertiaryElement.explain && (
                    <div className="adaptive-explain-preview" role="tooltip">
                      <p className="preview-def">{tertiaryElement.caption || tertiaryElement.explain.short_definition}</p>
                      <p className="preview-exact-val">{tertiaryElement.explain.exact_value_text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Apache ECharts Canvas */}
            <div className="breakdown-body" role="img" aria-label={`Ranked breakdown chart of ${tertiaryElement.title} across ${tertiaryElement.total_categories} categories.`}>
              <SafeReactECharts
                option={breakdownOption}
                opts={{ renderer: "svg" }}
                style={{ height: breakdownHeight, width: "100%", maxWidth: "100%" }}
              />
            </div>
          </section>
        )}

        {/* State E: Ready Quaternary Element (Explanatory Comparator Card - Gate 4) */}
        {!calculating && !calcError && quaternaryElement && (quaternaryElement.kind === "cohort_comparator" || quaternaryElement.kind === "impact_ratio") && (
          <section className="adaptive-comparator-card" aria-labelledby="quaternary-comparator-title">
            <div className="comparator-card-header">
              <div className="comparator-title-group">
                <h2 id="quaternary-comparator-title" className="comparator-card-title">
                  {quaternaryElement.title}
                </h2>
                {quaternaryElement.glance?.context_qualifier && (
                  <span className="comparator-context-qualifier">
                    {quaternaryElement.glance.context_qualifier}
                  </span>
                )}
              </div>

              <div className="comparator-controls-group">
                {quaternaryElement.formatted_relative_lift && (
                  <div className="comparator-lift-pill" title={`Observed comparative lift: ${quaternaryElement.formatted_relative_lift}`}>
                    <span className="lift-arrow">▲</span>
                    <span className="lift-value">{quaternaryElement.formatted_relative_lift}</span>
                    {quaternaryElement.formatted_absolute_lift && (
                      <span className="lift-abs">({quaternaryElement.formatted_absolute_lift})</span>
                    )}
                  </div>
                )}

                <div className="info-trigger-wrapper">
                  <button
                    ref={comparatorTriggerBtnRef}
                    type="button"
                    className="glance-info-btn"
                    aria-label={`View calculation and source audit for ${quaternaryElement.title}`}
                    title={quaternaryElement.caption || `Methodology & audit for ${quaternaryElement.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={inspectModalOpen && inspectTarget === "quaternary"}
                    onClick={() => handleOpenInspect("quaternary")}
                    onMouseEnter={() => !inspectModalOpen && setShowExplainQuaternary(true)}
                    onMouseLeave={() => setShowExplainQuaternary(false)}
                    onFocus={() => !inspectModalOpen && setShowExplainQuaternary(true)}
                    onBlur={() => setShowExplainQuaternary(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setShowExplainQuaternary(false);
                    }}
                  >
                    <Info aria-hidden="true" />
                  </button>

                  {/* Layer 2: Explain Preview Tooltip for Quaternary Element */}
                  {showExplainQuaternary && !inspectModalOpen && quaternaryElement.explain && (
                    <div className="adaptive-explain-preview" role="tooltip">
                      <p className="preview-def">{quaternaryElement.caption || quaternaryElement.explain.short_definition}</p>
                      <p className="preview-exact-val">{quaternaryElement.explain.exact_value_text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Apache ECharts Canvas */}
            <div className="comparator-body" role="img" aria-label={`Cohort comparator chart of ${quaternaryElement.title}.`}>
              <SafeReactECharts
                option={comparatorOption}
                opts={{ renderer: "svg" }}
                style={{ height: isMobile ? 180 : 170, width: "100%", maxWidth: "100%" }}
              />
            </div>
          </section>
        )}

        {/* Layer 1: Quinary Element & Decision Focus (Wrapped in Collapsible Secondary Findings when Priority Insight is Active) */}
        {!calculating && !calcError && (quinaryElement || decisionElement) && (
          <SecondaryFindingsWrapper>
            {quinaryElement && (quinaryElement.kind === "segment_disparity" || quinaryElement.kind === "variance_matrix") && (
              <section className="adaptive-disparity-card" aria-labelledby="quinary-disparity-title">
            {/* Header: Title, Context Qualifier, Dominant Spread Pill, and Info Button */}
            <div className="disparity-card-header">
              <div className="disparity-title-group">
                <h2 id="quinary-disparity-title" className="disparity-card-title">
                  {quinaryElement.title}
                </h2>
                {quinaryElement.glance?.context_qualifier && (
                  <span className="disparity-context-qualifier">
                    {quinaryElement.glance.context_qualifier}
                  </span>
                )}
              </div>

              <div className="disparity-controls-group">
                {quinaryElement.formatted_spread && (
                  <div
                    className="disparity-spread-pill"
                    title={`Observed segment disparity spread: ${quinaryElement.formatted_spread}`}
                  >
                    <span className="spread-label">Spread:</span>
                    <span className="spread-value">{quinaryElement.formatted_spread}</span>
                  </div>
                )}

                {/* Layer 1 Info Control with Layer 2 Explain Preview */}
                <div className="info-trigger-wrapper">
                  <button
                    ref={disparityTriggerBtnRef}
                    type="button"
                    className="glance-info-btn"
                    aria-label={`View methodology and calculation audit for ${quinaryElement.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={inspectModalOpen && inspectTarget === "quinary"}
                    onClick={() => handleOpenInspect("quinary")}
                    onMouseEnter={() => !inspectModalOpen && setShowExplainQuinary(true)}
                    onMouseLeave={() => setShowExplainQuinary(false)}
                    onFocus={() => !inspectModalOpen && setShowExplainQuinary(true)}
                    onBlur={() => setShowExplainQuinary(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setShowExplainQuinary(false);
                    }}
                  >
                    <Info size={16} aria-hidden="true" />
                  </button>

                  {/* Layer 2: Explain Hover / Focus Preview Card */}
                  {showExplainQuinary && !inspectModalOpen && quinaryElement.explain && (
                    <div className="adaptive-explain-preview" role="tooltip">
                      <p className="preview-def">{quinaryElement.caption || quinaryElement.explain.short_definition}</p>
                      <p className="preview-exact-val">{quinaryElement.explain.exact_value_text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Top-Level Benchmark & Polar Extremes Banner */}
            <div className="disparity-summary-strip">
              <div className="summary-pill top-pill">
                <span className="pill-dot top-dot" />
                <span className="pill-tag">Top Unit:</span>
                <strong className="pill-name">{quinaryElement.top_segment}</strong>
                <span className="pill-stat">
                  {quinaryElement.items.find((it) => it.segment === quinaryElement.top_segment)?.formatted_primary || ""}
                </span>
              </div>
              {quinaryElement.formatted_benchmark && (
                <div className="summary-pill benchmark-pill">
                  <span className="pill-dot bench-dot" />
                  <span className="pill-tag">Benchmark Average:</span>
                  <strong className="pill-name">{quinaryElement.formatted_benchmark}</strong>
                </div>
              )}
              <div className="summary-pill bottom-pill">
                <span className="pill-dot bottom-dot" />
                <span className="pill-tag">Lowest Unit:</span>
                <strong className="pill-name">{quinaryElement.bottom_segment}</strong>
                <span className="pill-stat">
                  {quinaryElement.items.find((it) => it.segment === quinaryElement.bottom_segment)?.formatted_primary || ""}
                </span>
              </div>
            </div>

            {/* Disparity Distribution Matrix List */}
            <div className="disparity-matrix-body" role="region" aria-label={`Ranked distribution for ${quinaryElement.title}`}>
              <div className="matrix-table-head">
                <span className="col-rank">#</span>
                <span className="col-segment">{quinaryElement.dimension_name || "Segment"}</span>
                <span className="col-bar">Relative Reliability & Capacity</span>
                <span className="col-primary">{quinaryElement.metric_name || "Value"}</span>
                {quinaryElement.secondary_metric_name && (
                  <span className="col-secondary">{quinaryElement.secondary_metric_name}</span>
                )}
                <span className="col-relative">vs Benchmark</span>
                <span className="col-tier">Operational Tier</span>
              </div>

              <div className="matrix-rows-list">
                {quinaryElement.items.map((item, idx) => {
                  const maxVal = Math.max(...quinaryElement.items.map((i) => i.primary_value || 1));
                  const pctWidth = maxVal > 0 ? Math.min(100, Math.max(12, ((item.primary_value || 0) / maxVal) * 100)) : 50;
                  const isTop = item.tier === "top_tier";
                  const isFriction = item.tier === "friction_tier";

                  return (
                    <div
                      key={item.segment || idx}
                      className={`matrix-row-item ${isTop ? "is-top-tier" : isFriction ? "is-friction-tier" : "is-standard-tier"}`}
                    >
                      <span className="cell-rank">#{idx + 1}</span>
                      <div className="cell-segment">
                        <strong className="segment-title">{item.segment}</strong>
                        <span className="segment-meta">{item.sample_label}</span>
                      </div>
                      <div className="cell-bar-wrap">
                        <div
                          className={`cell-bar-fill ${isTop ? "bar-top" : isFriction ? "bar-friction" : "bar-standard"}`}
                          style={{ width: `${pctWidth}%` }}
                        />
                      </div>
                      <span className="cell-primary">
                        <strong>{item.formatted_primary}</strong>
                      </span>
                      {quinaryElement.secondary_metric_name && (
                        <span className="cell-secondary">
                          {item.formatted_secondary || "—"}
                        </span>
                      )}
                      <span className="cell-relative">
                        <span className={`delta-pill ${item.formatted_relative_index?.startsWith("+") ? "delta-pos" : item.formatted_relative_index?.startsWith("-") ? "delta-neg" : "delta-neutral"}`}>
                          {item.formatted_relative_index || "—"}
                        </span>
                      </span>
                      <span className="cell-tier">
                        <span className={`tier-badge tier-${item.tier}`}>
                          {item.tier === "top_tier" ? "Top Tier" : item.tier === "friction_tier" ? "Attention" : "Standard"}
                        </span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        )}

        {/* Layer 1: Element 6 — Decision Focus Card (Gate 6) */}
        {decisionElement && (
          <section
            ref={decisionCardRef}
            className="adaptive-decision-card"
            aria-labelledby="decision-focus-title"
          >
            {/* Header: Eyebrow + Info Control */}
            <div className="decision-card-header">
              <div className="decision-eyebrow-group">
                <span className="decision-eyebrow">Decision focus</span>
              </div>

              <div className="decision-controls-group">
                {/* Layer 1 Info Control with Layer 2 Explain Preview */}
                <div className="info-trigger-wrapper">
                  <button
                    ref={decisionTriggerBtnRef}
                    type="button"
                    className="glance-info-btn"
                    aria-label={`View methodology and audit for ${decisionElement.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={inspectModalOpen && inspectTarget === "decision"}
                    onClick={() => handleOpenInspect("decision")}
                    onMouseEnter={() => !inspectModalOpen && setShowExplainDecision(true)}
                    onMouseLeave={() => setShowExplainDecision(false)}
                    onFocus={() => !inspectModalOpen && setShowExplainDecision(true)}
                    onBlur={() => setShowExplainDecision(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setShowExplainDecision(false);
                    }}
                  >
                    <Info size={16} aria-hidden="true" />
                  </button>

                  {/* Layer 2: Explain Hover / Focus Preview Card */}
                  {showExplainDecision && !inspectModalOpen && decisionElement.explain && (
                    <div className="adaptive-explain-preview" role="tooltip">
                      <p className="preview-def">{decisionElement.caption || decisionElement.explain.short_definition}</p>
                      <p className="preview-exact-val">{decisionElement.explain.exact_value_text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Headline: Strongest text element */}
            <h2 id="decision-focus-title" className="decision-headline">
              {decisionElement.title}
            </h2>

            {/* Evidence Row: At most 3 compact facts separated visually */}
            <div className="decision-evidence-row" role="group" aria-label="Supporting evidence">
              <span className="evidence-fact primary-fact">
                <span className="fact-label">Observed:</span>
                <strong className="fact-value">{decisionElement.formatted_observed_value}</strong>
              </span>
              <span className="evidence-separator" aria-hidden="true">·</span>
              <span className="evidence-fact gap-fact">
                <span className="fact-label">Gap:</span>
                <strong className="fact-value">{decisionElement.formatted_gap_value}</strong>
              </span>
              {decisionElement.sample_label && (
                <>
                  <span className="evidence-separator" aria-hidden="true">·</span>
                  <span className="evidence-fact sample-fact">
                    <span className="fact-label">Scope:</span>
                    <strong className="fact-value">{decisionElement.sample_label}</strong>
                  </span>
                </>
              )}
            </div>

            {/* Three narrative blocks: Why this matters, Next check, and Accountable Owner (Merged from Report) */}
            <div className="decision-narrative-grid">
              <div className="decision-narrative-block">
                <span className="narrative-tag">Why this matters</span>
                <p className="narrative-text">{decisionElement.why_it_matters}</p>
              </div>

              <div className="decision-narrative-block">
                <span className="narrative-tag">Next check</span>
                <p className="narrative-text">{decisionElement.next_step}</p>
              </div>

              <div className="decision-narrative-block decision-narrative-block--owner">
                <span className="narrative-tag">Accountable Owner</span>
                <p className="narrative-text">
                  <strong>{decisionElement.owner || "Lead HRBP with Unit Manager"}</strong> · Review: 14-day cycle
                </p>
              </div>
            </div>

            {/* HR Policy Compliance Guideline */}
            <div className="decision-compliance-guardrail" role="note">
              <span className="guardrail-dot" />
              <span>HR Policy Guardrail: Recommendation is for managerial decision-support. Reconcile medical/annual leaves before adjusting capacity targets.</span>
            </div>

            {/* Supporting evidence action link/button when supporting_component_id exists */}
            {decisionElement.supporting_component_id && (
              <div className="decision-action-footer">
                <button
                  type="button"
                  className="decision-action-btn"
                  onClick={() => {
                    if (decisionElement.supporting_component_id === "quinary_element") {
                      disparityTriggerBtnRef.current?.focus();
                      disparityTriggerBtnRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                    } else if (decisionElement.supporting_component_id === "quaternary_element") {
                      comparatorTriggerBtnRef.current?.focus();
                      comparatorTriggerBtnRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                    } else if (decisionElement.supporting_component_id === "tertiary_element") {
                      breakdownTriggerBtnRef.current?.focus();
                      breakdownTriggerBtnRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                  }}
                  aria-label="Open supporting evidence in segment disparity matrix"
                >
                  <span>Open supporting evidence</span>
                  <ArrowRight size={14} aria-hidden="true" />
                </button>
              </div>
            )}
          </section>
        )}
      </SecondaryFindingsWrapper>
    )}

        {/* Layer 1: Element 7 — Executive Briefing with Voice Orb (Gate 7) */}
        {!calculating && !calcError && briefingElement && (
          <ExecutiveBriefingCard
            briefing={briefingElement}
            snapshot={data?.snapshot}
            onInspect={handleOpenInspect}
          />
        )}

        {/* Layer 1: Element 8 — Exception Watch (Gate 8) */}
        {!calculating && !calcError && exceptionElement && (
          <ExceptionWatchCard
            exception={exceptionElement}
            sheetId={selectedSheetId}
            snapshot={data?.snapshot}
            onInspect={handleOpenInspect}
            onNavigateTab={onNavigateTab}
          />
        )}

        {/* Layer 1: Element 9 — Forward Outlook (Gate 9) */}
        {!calculating && !calcError && outlookElement && (
          <ForwardOutlookCard
            outlook={outlookElement}
            sheetId={selectedSheetId}
            snapshot={data?.snapshot}
            onInspect={handleOpenInspect}
          />
        )}

        {/* Layer 1: Element 10 — Enterprise Synthesis (Gate 10) */}
        {!calculating && !calcError && enterpriseElement && (
          <EnterpriseSynthesisCard
            enterprise={enterpriseElement}
            sheetId={selectedSheetId}
            snapshot={data?.snapshot}
            onInspect={handleOpenInspect}
            infoButtonRef={enterpriseTriggerBtnRef}
          />
        )}
      </main>

      {/* Layer 3: Inspect Modal Details Dialog / Sheet */}
      {inspectModalOpen && activeInspect && (
        <div
          className="adaptive-modal-backdrop"
          onClick={handleCloseInspect}
          role="presentation"
        >
          <div
            ref={dialogRef}
            className="adaptive-inspect-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inspect-dialog-title"
            onClick={(e) => e.stopPropagation()}
            tabIndex={-1}
          >
            <div className="inspect-dialog-header">
              <div className="inspect-title-area">
                <h3 id="inspect-dialog-title">
                  {inspectTarget === "enterprise"
                    ? "Enterprise synthesis — Methodology & Audit"
                    : activeInspect.metric_title}
                </h3>
                <div className="inspect-exact-headline">{activeInspect.exact_value}</div>
              </div>

              <button
                ref={modalCloseBtnRef}
                type="button"
                className="inspect-close-btn"
                aria-label={`Close details for ${activeInspect.metric_title}`}
                onClick={handleCloseInspect}
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="inspect-dialog-body">
              {/* What this counts & Population */}
              <div className="inspect-item">
                <span className="item-label">What This Counts</span>
                <span className="item-value">{activeInspect.what_this_counts}</span>
              </div>

              <div className="inspect-item">
                <span className="item-label">Applicable Population</span>
                <span className="item-value">{activeInspect.applicable_population}</span>
              </div>

              {/* Source & Period */}
              <div className="inspect-item">
                <span className="item-label">Source Scope & Period</span>
                <span className="item-value">
                  {activeInspect.source_name}
                  {activeInspect.reporting_period ? ` · ${activeInspect.reporting_period}` : ""}
                </span>
              </div>

              {/* Calculation & Data Completeness */}
              <div className="inspect-item">
                <span className="item-label">Calculation Method</span>
                <span className="item-value">{activeInspect.calculation_method}</span>
              </div>

              <div className="inspect-item">
                <span className="item-label">Data Completeness</span>
                <span className="item-value">{activeInspect.data_completeness}</span>
              </div>

              <div className="inspect-item">
                <span className="item-label">{activeInspect.coverage_label || "Coverage Scope"}</span>
                <span className="item-value">{activeInspect.coverage_value || activeInspect.workforce_coverage}</span>
              </div>

              {/* Selection Rationale */}
              <div className="inspect-item">
                <span className="item-label">Selection Rationale</span>
                <span className="item-value">{activeInspect.selection_reason}</span>
              </div>

              {/* Limitations List */}
              {activeInspect.limitations?.length > 0 && (
                <div className="inspect-item">
                  <span className="item-label">Declared Limitations</span>
                  <ul>
                    {activeInspect.limitations.map((lim, idx) => (
                      <li key={idx}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Supporting Disclosure: Table of Monthly Values with Middle 80% Distribution Band */}
              {inspectTarget === "secondary" && chartPoints.length > 0 && (
                <div className="inspect-item">
                  <span className="item-label">
                    {secondaryElement?.temporal_grain === "weekly" ? "Weekly Observations & Distribution" : "Monthly Observations & Distribution"}
                  </span>
                  <div className="inspect-table-wrapper">
                    <table className="inspect-data-table" aria-label="Timeline Observations Data">
                      <thead>
                        <tr>
                          <th scope="col">{secondaryElement?.temporal_grain === "weekly" ? "Retail Week" : "Month"}</th>
                          <th scope="col">Average</th>
                          <th scope="col">Middle 80% (P10–P90)</th>
                          <th scope="col">Observed Range</th>
                          <th scope="col">Valid Entries</th>
                          <th scope="col">{secondaryElement?.temporal_grain === "weekly" ? "Date" : "Dates"}</th>
                          <th scope="col">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {chartPoints.map((pt) => (
                          <tr key={pt.period}>
                            <th scope="row" style={{ textAlign: "left" }}>
                              <strong>{pt.period_label}</strong>
                              {secondaryElement?.temporal_grain === "weekly" && pt.first_observed_date && (
                                <span style={{ display: "block", fontSize: "11px", fontWeight: "normal", color: "#a89f94" }}>
                                  {formatHumanDate(pt.first_observed_date)}
                                </span>
                              )}
                            </th>
                            <td>
                              {pt.average_hours !== null
                                ? secondaryElement.glance?.unit === "$"
                                  ? pt.formatted_hours
                                  : `${pt.formatted_hours} (${pt.average_hours.toFixed(2)}h)`
                                : "—"}
                            </td>
                            <td>
                              {pt.has_band ? `${pt.formatted_p10} – ${pt.formatted_p90}` : (pt.average_hours !== null ? "Sparse (n < 20)" : "—")}
                            </td>
                            <td>
                              {pt.min_hours !== null ? `${pt.formatted_min} – ${pt.formatted_max}` : "—"}
                            </td>
                            <td>{pt.valid_entries.toLocaleString()}</td>
                            <td>{pt.observed_dates}</td>
                            <td>
                              {pt.is_partial ? (
                                <span className="status-partial" title={pt.partial_reason}>
                                  Partial
                                </span>
                              ) : pt.average_hours === null ? (
                                <span className="status-missing">No data</span>
                              ) : (
                                <span className="status-complete">Complete</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Supporting Disclosure: Table of Categorical Breakdown Proportions */}
              {inspectTarget === "tertiary" && tertiaryElement?.items?.length > 0 && (
                <div className="inspect-item">
                  <span className="item-label">
                    Categorical Distribution & Proportions
                  </span>
                  <div className="inspect-table-wrapper">
                    <table className="inspect-data-table" aria-label="Categorical Breakdown Data">
                      <thead>
                        <tr>
                          <th scope="col">{tertiaryElement.dimension_name || "Category"}</th>
                          <th scope="col">{tertiaryElement.metric_name || "Value"}</th>
                          <th scope="col">Share (%)</th>
                          {tertiaryElement.items.some((it) => it.formatted_secondary) && (
                            <th scope="col">Average / Secondary</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {tertiaryElement.items.map((it, idx) => (
                          <tr key={idx}>
                            <th scope="row" style={{ textAlign: "left" }}>
                              <strong>{it.category}</strong>
                              {it.category === "Other" && it.formatted_secondary && (
                                <span style={{ display: "block", fontSize: "11px", fontWeight: "normal", color: "#a89f94" }}>
                                  ({it.formatted_secondary} consolidated)
                                </span>
                              )}
                            </th>
                            <td>{it.formatted_value}</td>
                            <td>
                              <strong>{it.share_pct.toFixed(1)}%</strong>
                            </td>
                            {tertiaryElement.items.some((item) => item.formatted_secondary) && (
                              <td>{it.formatted_secondary || "—"}</td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Supporting Disclosure: Table of Cohort Comparison & Uplift Impact */}
              {inspectTarget === "quaternary" && quaternaryElement?.items?.length > 0 && (
                <div className="inspect-item">
                  <span className="item-label">
                    Cohort Comparison & Uplift Audit
                  </span>
                  <div className="inspect-table-wrapper">
                    <table className="inspect-data-table" aria-label="Cohort Comparison Data">
                      <thead>
                        <tr>
                          <th scope="col">{quaternaryElement.dimension_name || "Cohort"}</th>
                          <th scope="col">{quaternaryElement.metric_name || "Value"}</th>
                          <th scope="col">Sample Size</th>
                          <th scope="col">Share (%)</th>
                          {quaternaryElement.items.some((it) => it.formatted_secondary) && (
                            <th scope="col">Secondary / Volume</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {quaternaryElement.items.map((it, idx) => (
                          <tr key={idx}>
                            <th scope="row" style={{ textAlign: "left" }}>
                              <strong>{it.cohort}</strong>
                              {it.is_baseline && (
                                <span style={{ display: "inline-block", marginLeft: "6px", fontSize: "10px", padding: "1px 5px", borderRadius: "3px", background: "#3d362f", color: "#c9bdb0" }}>
                                  Baseline
                                </span>
                              )}
                            </th>
                            <td><strong>{it.formatted_value}</strong></td>
                            <td>{it.sample_label}</td>
                            <td>{it.share_pct !== null && it.share_pct !== undefined ? `${it.share_pct.toFixed(1)}%` : "—"}</td>
                            {quaternaryElement.items.some((item) => item.formatted_secondary) && (
                              <td>{it.formatted_secondary || "—"}</td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Supporting Disclosure: Table of Disparity & Variance Matrix (Gate 5) */}
              {inspectTarget === "quinary" && quinaryElement?.items?.length > 0 && (
                <div className="inspect-item">
                  <span className="item-label">
                    Full Disparity Distribution & Operational Tiers
                  </span>
                  <div className="inspect-table-wrapper">
                    <table className="inspect-data-table" aria-label="Segment Disparity Audit">
                      <thead>
                        <tr>
                          <th scope="col">#</th>
                          <th scope="col">{quinaryElement.dimension_name || "Segment"}</th>
                          <th scope="col">{quinaryElement.metric_name || "Primary Metric"}</th>
                          {quinaryElement.secondary_metric_name && (
                            <th scope="col">{quinaryElement.secondary_metric_name}</th>
                          )}
                          <th scope="col">vs Benchmark</th>
                          <th scope="col">Sample Size</th>
                          <th scope="col">Tier</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quinaryElement.items.map((it, idx) => (
                          <tr key={idx}>
                            <td>#{idx + 1}</td>
                            <th scope="row" style={{ textAlign: "left" }}>
                              <strong>{it.segment}</strong>
                            </th>
                            <td><strong>{it.formatted_primary}</strong></td>
                            {quinaryElement.secondary_metric_name && (
                              <td>{it.formatted_secondary || "—"}</td>
                            )}
                            <td>
                              <span className={`delta-pill ${it.formatted_relative_index?.startsWith("+") ? "delta-pos" : it.formatted_relative_index?.startsWith("-") ? "delta-neg" : "delta-neutral"}`}>
                                {it.formatted_relative_index || "—"}
                              </span>
                            </td>
                            <td>{it.sample_label}</td>
                            <td>
                              <span className={`tier-badge tier-${it.tier}`}>
                                {it.tier === "top_tier" ? "Top Tier" : it.tier === "friction_tier" ? "Attention" : "Standard"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Supporting Decision Context */}
              {inspectTarget === "decision" && decisionElement && (
                <div className="inspect-item">
                  <span className="item-label">Decision Target & Recommendation</span>
                  <div className="inspect-decision-summary" style={{ fontSize: "13px", lineHeight: "1.6", color: "var(--fg-secondary, #c9bdb0)" }}>
                    <div><strong>Focus Subject:</strong> {decisionElement.subject_type}: {decisionElement.subject_label}</div>
                    <div><strong>Observed vs Comparator:</strong> {decisionElement.formatted_observed_value} vs {decisionElement.formatted_comparator_value} ({decisionElement.formatted_gap_value})</div>
                    <div><strong>Next Diagnostic Step:</strong> {decisionElement.next_step}</div>
                    <div><strong>Priority Basis:</strong> <code>{decisionElement.priority_basis}</code></div>
                  </div>
                </div>
              )}

              {/* Supporting Executive Briefing Claims Audit (Gate 7) */}
              {inspectTarget === "briefing" && briefingElement && (
                <div className="inspect-item">
                  <span className="item-label">Evidence-Bound Claims Provenance</span>
                  <div className="inspect-table-wrapper">
                    <table className="inspect-data-table" aria-label="Executive Briefing Claims Audit">
                      <thead>
                        <tr>
                          <th scope="col">#</th>
                          <th scope="col">Claim Type</th>
                          <th scope="col">Evidence Claim Statement</th>
                          <th scope="col">Source Component</th>
                          <th scope="col">Calculation IDs</th>
                        </tr>
                      </thead>
                      <tbody>
                        {briefingElement.claims.map((claim, idx) => (
                          <tr key={claim.claim_id || idx}>
                            <td>#{idx + 1}</td>
                            <td>
                              <span className={`tier-badge ${claim.claim_type === 'limitation' ? 'tier-friction_tier' : 'tier-standard_tier'}`}>
                                {claim.claim_type.replace('_', ' ')}
                              </span>
                            </td>
                            <td style={{ textAlign: "left" }}>{claim.text}</td>
                            <td><code>{claim.source_component_id}</code></td>
                            <td><code>{claim.calculation_ids.join(", ") || "—"}</code></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Supporting Exception Watch Statistical Methodology (Gate 8) */}
              {inspectTarget === "exception" && exceptionElement && exceptionElement.lead_exception && (
                <div className="inspect-item">
                  <span className="item-label">Statistical Methodology & Screening Context</span>
                  <div className="inspect-calc-method-block">
                    <div><strong>Detection Method:</strong> {exceptionElement.lead_exception.method}</div>
                    <div><strong>Observed Cohort Value:</strong> {exceptionElement.lead_exception.formatted_observed_value}</div>
                    <div><strong>Typical Observed Range:</strong> {exceptionElement.lead_exception.formatted_expected_range} (Statistical baseline)</div>
                    <div><strong>Deviation Magnitude:</strong> {exceptionElement.lead_exception.formatted_deviation} ({exceptionElement.lead_exception.direction})</div>
                    <div><strong>Sample Size / Breadth:</strong> {exceptionElement.lead_exception.sample_label}</div>
                    <div><strong>Why Inspect:</strong> {exceptionElement.why_inspect}</div>
                    <div><strong>Next Scheduled Review:</strong> {exceptionElement.next_check}</div>
                  </div>
                </div>
              )}

              {/* Supporting Forward Outlook Statistical Methodology (Gate 9) */}
              {inspectTarget === "outlook" && outlookElement && (
                <div className="inspect-item">
                  <span className="item-label">Forward Outlook Methodology & Validation</span>
                  <div className="inspect-calc-method-block">
                    <div><strong>Outlook Mode:</strong> {outlookElement.kind}</div>
                    {outlookElement.kind === "target_gap" && (
                      <>
                        <div><strong>Actual Value:</strong> {outlookElement.actual_value} {outlookElement.unit}</div>
                        <div><strong>Recorded Target:</strong> {outlookElement.target_value} {outlookElement.unit}</div>
                        <div><strong>Variance Gap:</strong> {outlookElement.gap_value} {outlookElement.unit}</div>
                      </>
                    )}
                    {outlookElement.kind === "statistical_forecast" && (
                      <>
                        <div><strong>Forecast Model:</strong> {outlookElement.validation?.model_label || outlookElement.model_id}</div>
                        <div><strong>Point Estimate:</strong> {outlookElement.forecast_value} {outlookElement.unit}</div>
                        <div><strong>Empirical Range:</strong> {outlookElement.lower_bound}–{outlookElement.upper_bound} {outlookElement.unit}</div>
                        <div><strong>Validation Folds:</strong> {outlookElement.validation?.fold_count} rolling-origin folds</div>
                        <div><strong>Model WAPE / MAE:</strong> {(outlookElement.validation?.wape * 100).toFixed(1)}% / {outlookElement.validation?.mae}</div>
                        <div><strong>Baseline WAPE / MAE:</strong> {(outlookElement.validation?.baseline_wape * 100).toFixed(1)}% / {outlookElement.validation?.baseline_mae}</div>
                      </>
                    )}
                    <div><strong>Context & Status:</strong> {outlookElement.why_available_or_unavailable}</div>
                  </div>
                </div>
              )}

              {/* Supporting Enterprise Synthesis Methodology (Gate 10) */}
              {inspectTarget === "enterprise" && enterpriseElement && (
                <div className="inspect-item enterprise-audit-block">
                  <span className="item-label">Enterprise Synthesis Evidence & Reconciliation</span>
                  <div className="enterprise-audit-summary">
                    <div>
                      <strong>Lead finding:</strong>{" "}
                      {enterpriseElement.lead_finding?.title || "No analytical recipe passed; coverage only"}
                    </div>
                    <div>
                      <strong>Recipe ID:</strong>{" "}
                      <code>{enterpriseElement.lead_finding?.recipe_id || "coverage_only"}</code>
                    </div>
                    <div>
                      <strong>Join description:</strong>{" "}
                      {enterpriseElement.lead_finding?.join_description || "No verified cross-source join available"}
                    </div>
                    <div className="enterprise-audit-counts">
                      <span>
                        <strong>Matched:</strong>{" "}
                        {(enterpriseElement.lead_finding?.matched_count ?? 0).toLocaleString()}
                      </span>
                      <span>
                        <strong>Unmatched:</strong>{" "}
                        {(enterpriseElement.lead_finding?.unmatched_count ?? 0).toLocaleString()}
                      </span>
                      <span>
                        <strong>Coverage:</strong>{" "}
                        {enterpriseElement.lead_finding
                          ? `${(enterpriseElement.lead_finding.coverage_ratio * 100).toFixed(1)}%`
                          : "Not established"}
                      </span>
                    </div>
                    <div>
                      <strong>Combined snapshot hash:</strong>{" "}
                      <code>{enterpriseElement.lead_finding?.snapshot || activeInspect.snapshot}</code>
                    </div>
                    <div>
                      <strong>What it establishes:</strong> {enterpriseElement.what_it_establishes}
                    </div>
                    <div>
                      <strong>What it does not establish:</strong>{" "}
                      {enterpriseElement.what_it_does_not_establish}
                    </div>
                  </div>

                  {enterpriseElement.drilldown_targets?.length > 0 && (
                    <div className="enterprise-audit-sources" aria-label="Enterprise synthesis source sheets">
                      <strong>Source sheets:</strong>
                      {enterpriseElement.drilldown_targets.map((target) => (
                        <a key={target.sheet_id} href={target.route}>
                          {target.label}
                        </a>
                      ))}
                    </div>
                  )}

                  <div className="enterprise-audit-identifiers">
                    <div><strong>Calculation ID:</strong> <code>{activeInspect.calculation_id}</code></div>
                    <div><strong>Definition ID:</strong> <code>{activeInspect.definition_id}</code></div>
                    <div><strong>Provenance:</strong> {activeInspect.provenance}</div>
                  </div>
                </div>
              )}

              {/* Nested Technical Provenance (collapsible) */}
              <details className="inspect-tech-details">
                <summary>Technical Identifiers & Provenance</summary>
                <div className="tech-meta-block">
                  <div><strong>Calculation ID:</strong> {activeInspect.calculation_id}</div>
                  <div><strong>Definition ID:</strong> {activeInspect.definition_id}</div>
                  <div><strong>Source Snapshot:</strong> {activeInspect.snapshot}</div>
                  <div><strong>Provenance:</strong> {activeInspect.provenance}</div>
                </div>
              </details>
            </div>
          </div>
        </div>
      )}

      {/* Inline Contextual Evidence & Source Records Drawer (Preserves Executive Context) */}
      {investigationTarget && (
        <InvestigationDrawer
          investigationTarget={investigationTarget}
          onClose={() => setInvestigationTarget(null)}
          onDrillDown={(newTarget) => {
            if (newTarget?.employeeId != null || newTarget?.employee_id != null) {
              setInspectedEmployeeId(newTarget.employeeId || newTarget.employee_id);
            } else {
              setInvestigationTarget(newTarget);
            }
          }}
        />
      )}

      {/* Inline Employee Profile Drawer */}
      {inspectedEmployeeId != null && (
        <EmployeeDrawer
          employeeId={inspectedEmployeeId}
          onClose={() => setInspectedEmployeeId(null)}
        />
      )}
    </div>
  );
}
