"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/useAuthStore";

export default function Home() {
  const router = useRouter();
  const { user, token } = useAuthStore();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    } else if (user?.role === "doctor") {
      router.replace("/doctor");
    } else {
      router.replace("/patient");
    }
  }, [token, user, router]);

  return null;
}
