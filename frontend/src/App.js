import "@/index.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "sonner";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import ForgotPassword from "@/pages/ForgotPassword";
import AuthCallback from "@/pages/AuthCallback";
import MemberDashboard from "@/pages/MemberDashboard";
import PublicGallery from "@/pages/PublicGallery";
import { Overview, Members, Events, Sessions, Gallery, Profile } from "@/pages/Admin";

function Router() {
  const location = useLocation();
  // Handle Google OAuth callback - session_id lands in URL fragment
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/gallery" element={<PublicGallery />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/member" element={<MemberDashboard />} />
      <Route path="/admin" element={<Overview />} />
      <Route path="/admin/members" element={<Members />} />
      <Route path="/admin/events" element={<Events />} />
      <Route path="/admin/sessions" element={<Sessions />} />
      <Route path="/admin/gallery" element={<Gallery />} />
      <Route path="/admin/profile" element={<Profile />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster theme="dark" position="top-right" richColors />
        <Router />
      </BrowserRouter>
    </AuthProvider>
  );
}
