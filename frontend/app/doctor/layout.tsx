import DoctorSidebar from "@/components/layout/DoctorSidebar";

export default function DoctorLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <DoctorSidebar />
      <div className="flex-1 ml-64 flex flex-col min-h-screen">{children}</div>
    </div>
  );
}
