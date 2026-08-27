export function categoryColor(category: string): string {
  if (category.includes("WEATHER") || category === "PORT_CLOSURE") return "bg-amber-100 text-amber-800";
  if (category === "SHIFTING" || category.includes("BERTH")) return "bg-purple-100 text-purple-800";
  if (category.includes("STRIKE") || category.includes("BREAKDOWN")) return "bg-red-100 text-red-800";
  if (category.includes("NOR") || category.includes("MOORED") || category === "ALL_FAST") return "bg-emerald-100 text-emerald-800";
  if (category.includes("LOADING") || category.includes("DISCHARGING") || category.includes("CARGO")) return "bg-blue-100 text-blue-800";
  if (category.includes("WAITING") || category.includes("AWAITING")) return "bg-orange-100 text-orange-800";
  return "bg-slate-100 text-slate-700";
}

export function confidenceColor(status: string): string {
  switch (status) {
    case "CONFIRMED":
      return "bg-emerald-100 text-emerald-800";
    case "PROBABLE":
      return "bg-blue-100 text-blue-800";
    case "NEEDS_REVIEW":
      return "bg-amber-100 text-amber-800";
    case "CONFLICTING_INFORMATION":
      return "bg-red-100 text-red-800";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export function eventStatusColor(status: string): string {
  switch (status) {
    case "CONFIRMED":
      return "bg-emerald-100 text-emerald-800";
    case "REJECTED":
      return "bg-red-100 text-red-800";
    case "EDITED":
      return "bg-blue-100 text-blue-800";
    default:
      return "bg-slate-100 text-slate-600";
  }
}
