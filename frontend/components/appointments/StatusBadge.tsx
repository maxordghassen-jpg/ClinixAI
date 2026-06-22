import { cn, STATUS_COLORS } from "@/lib/utils";
import type { AppointmentStatus } from "@/types";

const labels: Record<AppointmentStatus, string> = {
  confirmed: "Confirmed",
  pending:   "Pending",
  cancelled: "Cancelled",
  rejected:  "Rejected",
};

export default function StatusBadge({ status }: { status: AppointmentStatus }) {
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.pending;
  return (
    <span className={cn("badge", colors.bg, colors.text)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", colors.dot)} />
      {labels[status] ?? status}
    </span>
  );
}
