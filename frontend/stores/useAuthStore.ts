import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  email: string;
  name: string;
  role: "patient" | "doctor";
  patient_profile_id: string | null;
  doctor_id: string | null;
}

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  setAuth: (user: AuthUser, token: string) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user:  null,
      token: null,
      setAuth:         (user, token) => set({ user, token }),
      clearAuth:       ()            => set({ user: null, token: null }),
      isAuthenticated: ()            => !!get().token,
    }),
    { name: "clinix-auth" }
  )
);
