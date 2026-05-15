import { useState } from "react";
import { Outlet } from "@tanstack/react-router";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { cn } from "@/lib/utils";

export function MainLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Header onMenu={() => setOpen(true)} />
      <div className="flex flex-1">
        <div className="hidden lg:block">
          <Sidebar />
        </div>
        {/* Mobile drawer */}
        <div
          className={cn(
            "fixed inset-0 z-40 bg-background/70 backdrop-blur-sm transition lg:hidden",
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
          onClick={() => setOpen(false)}
        />
        <div
          className={cn(
            "fixed inset-y-0 left-0 z-50 w-64 transform transition lg:hidden",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <Sidebar onNavigate={() => setOpen(false)} />
        </div>

        <main className="min-w-0 flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
