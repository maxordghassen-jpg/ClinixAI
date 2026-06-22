"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Stethoscope, Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/useAuthStore";
import { authLogin } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authLogin({ email, password });

      setAuth(
        {
          email,
          name:  res.name,
          role:  res.role,
          patient_profile_id: res.patient_profile_id,
          doctor_id:          res.doctor_id,
        },
        res.access_token
      );

      document.cookie = `clinix-token=${res.access_token}; path=/; max-age=86400; SameSite=Lax`;

      router.push(res.role === "doctor" ? "/doctor" : "/patient");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md">
      {/* Logo */}
      <div className="flex items-center justify-center gap-2 mb-8">
        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-200">
          <Stethoscope size={20} className="text-white" />
        </div>
        <span className="text-xl font-bold text-slate-800">ClinixAI</span>
      </div>

      <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-1">Welcome back</h1>
        <p className="text-sm text-slate-500 mb-6">Sign in to your account to continue</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full px-3.5 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-3.5 py-2.5 pr-10 text-sm border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {error && (
            <p className="text-xs text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-semibold transition-colors shadow-md shadow-indigo-200"
          >
            {loading && <Loader2 size={15} className="animate-spin" />}
            Sign in
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-500">
          No account?{" "}
          <Link href="/signup" className="text-indigo-600 hover:text-indigo-700 font-semibold">
            Create one
          </Link>
        </p>

        {/* Demo hint */}
        <div className="mt-5 p-3 bg-slate-50 rounded-xl border border-slate-100">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Demo accounts</p>
          <p className="text-xs text-slate-600">Patient: <span className="font-mono">demo@patient.com</span> / <span className="font-mono">patient123</span></p>
          <p className="text-xs text-slate-600 mt-0.5">Doctor: <span className="font-mono">doc-001@clinix.ai</span> / <span className="font-mono">doctor123</span></p>
        </div>
      </div>
    </div>
  );
}
