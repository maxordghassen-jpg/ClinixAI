import TopBar from "@/components/layout/TopBar";
import MedicalProfileForm from "@/components/profile/MedicalProfileForm";

export default function PatientProfilePage() {
  return (
    <div className="flex flex-col min-h-full">
      <TopBar
        title="Medical Profile"
        subtitle="Your health information is shared only with doctors who have a confirmed appointment with you."
      />
      <div className="flex-1 p-6">
        <div className="max-w-2xl">
          <MedicalProfileForm />
        </div>
      </div>
    </div>
  );
}
