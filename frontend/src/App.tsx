import {
  HashRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  Bookmark,
  Database,
  Radio,
  Rss,
  Settings2,
  Radar,
  Code2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { useStats } from "./lib/hooks";
import { TooltipProvider } from "./components/ui/tooltip";
import Feed from "./pages/Feed";
import Sources from "./pages/Sources";
import Tasks from "./pages/Tasks";
import Settings from "./pages/Settings";
import Discover from "./pages/Discover";
import Projects from "./pages/Projects";
import "./discovery.css";
const nav = [
  { to: "/", label: "技术推荐", icon: Radar },
  { to: "/projects", label: "开源项目", icon: Code2 },
  { to: "/feed", label: "资讯库", icon: Rss },
  { to: "/favorites", label: "我的收藏", icon: Bookmark },
  { to: "/sources", label: "信息来源", icon: Radio },
  { to: "/tasks", label: "运行任务", icon: Activity },
  { to: "/settings", label: "系统设置", icon: Settings2 },
];
function Workspace() {
  const stats = useStats();
  const location = useLocation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ status: string }>("/health"),
    refetchInterval: 15000,
  });
  const current = nav.find((item) => item.to === location.pathname);
  return (
    <div className="workspace">
      <aside className="sidebar">
        <NavLink className="brand" to="/">
          <span className="brand-symbol">
            <Radio size={23} />
          </span>
          <span>
            FrontierSignal<small>AI 情报工作台</small>
          </span>
        </NavLink>
        <div className="nav-caption">工作空间</div>
        <nav aria-label="主导航">
          {nav.map((item) => (
            <NavLink
              end
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <item.icon size={18} />
              <span className="nav-label">{item.label}</span>
              {item.to === "/feed" && (
                <span className="nav-count">{stats.data?.total ?? "—"}</span>
              )}
              {item.to === "/favorites" && (
                <span className="nav-count">
                  {stats.data?.favorites ?? "—"}
                </span>
              )}
              {item.to === "/tasks" && !!stats.data?.active_tasks && (
                <span className="nav-count">{stats.data.active_tasks}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span
            className={`status-dot ${health.isSuccess && !health.isError ? "online" : ""}`}
          />
          {health.isError
            ? "本地服务连接异常"
            : health.isSuccess
              ? "本地服务已连接"
              : "正在连接服务"}
          <small>个人工作空间 · 本地数据库</small>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <span>
            工作空间 <span className="breadcrumb-separator">/</span>{" "}
            <strong>{current?.label}</strong>
          </span>
          <span className="local-label">
            <Database size={16} /> 本地工作台
          </span>
        </header>
        <div className="page-content">
          <Routes>
            <Route path="/" element={<Discover />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/feed" element={<Feed key="all" />} />
            <Route
              path="/favorites"
              element={<Feed key="favorites" favorite />}
            />
            <Route path="/sources" element={<Sources />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
export default function App() {
  return (
    <HashRouter>
      <TooltipProvider delayDuration={250}>
        <Workspace />
      </TooltipProvider>
    </HashRouter>
  );
}
