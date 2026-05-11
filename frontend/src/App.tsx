import { Routes, Route } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { ToasterProvider } from "@/components/Toaster";
import { Home } from "@/pages/Home";
import { AssignmentsPage } from "@/pages/Assignments";
import { AnnouncementsPage } from "@/pages/Announcements";
import { GradesPage } from "@/pages/Grades";
import { CoursePage } from "@/pages/Course";

export default function App() {
  return (
    <ToasterProvider>
      <div className="min-h-screen flex flex-col">
        <TopNav />
        <main className="container flex-1 py-6">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/assignments" element={<AssignmentsPage />} />
            <Route path="/announcements" element={<AnnouncementsPage />} />
            <Route path="/grades" element={<GradesPage />} />
            <Route path="/course/:id" element={<CoursePage />} />
          </Routes>
        </main>
        <footer className="border-t py-4 text-center text-xs text-muted-foreground">
          Personal use only · scrapes nightly
        </footer>
      </div>
    </ToasterProvider>
  );
}
