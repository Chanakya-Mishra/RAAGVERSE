import "@/index.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "sonner";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import ForgotPassword from "@/pages/ForgotPassword";
import { Overview, Members, Events, Sessions, Gallery, Profile } from "@/pages/Admin";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster theme="dark" position="top-right" richColors />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/admin" element={<Overview />} />
          <Route path="/admin/members" element={<Members />} />
          <Route path="/admin/events" element={<Events />} />
          <Route path="/admin/sessions" element={<Sessions />} />
          <Route path="/admin/gallery" element={<Gallery />} />
          <Route path="/admin/profile" element={<Profile />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
