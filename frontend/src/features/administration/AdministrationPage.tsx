import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ClipboardList,
  Download,
  FileText,
  HardHat,
  Landmark,
  LifeBuoy,
  Search,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { apiRequest, jsonBody } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { DashboardShell } from "../dashboard/DashboardShell";

const sections = [
  ["overview", "Vue d’ensemble", ClipboardList],
  ["users", "Utilisateurs et rôles", Users],
  ["companies", "Entreprises BTP", Building2],
  ["projects", "Projets et chantiers", HardHat],
  ["requests", "Demandes de services", FileText],
  ["teams", "Équipes et affectations", Users],
  ["missions", "Missions terrain", ClipboardList],
  ["reports", "Rapports et preuves", FileText],
  ["incidents", "Incidents et réclamations", AlertTriangle],
  ["payments", "Finances et paiements", Landmark],
  ["subscriptions", "Abonnements et offres", Landmark],
  ["communications", "Notifications et communications", Bell],
  ["support", "Support et assistance", LifeBuoy],
  ["analytics", "Statistiques et rapports", BarChart3],
  ["audit", "Journal d’audit", ShieldCheck],
  ["settings", "Paramètres", Settings],
] as const;
type Section = (typeof sections)[number][0];
type Dashboard = {
  period_days: number;
  statistics: Record<string, number | string>;
  series: Array<{
    date: string;
    users: number;
    projects: number;
    requests: number;
  }>;
  alerts: Array<{
    type: string;
    severity: string;
    title: string;
    detail: string;
    href: string;
  }>;
};
type Page = {
  results: Array<Record<string, unknown>>;
  count?: number;
  next?: string | null;
  previous?: string | null;
};
const resourceFor: Partial<Record<Section, string>> = {
  companies: "companies",
  projects: "projects",
  requests: "requests",
  missions: "missions",
  reports: "reports",
  incidents: "incidents",
  payments: "payments",
  subscriptions: "subscriptions",
  audit: "audit",
  support: "support",
  settings: "settings",
};

export function AdministrationPage() {
  const { section: raw = "overview" } = useParams();
  const section = (
    sections.some(([key]) => key === raw) ? raw : "overview"
  ) as Section;
  const { user, isReady, signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [period, setPeriod] = useState("30");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [feedback, setFeedback] = useState("");
  const allowed = user?.role === "ADMIN" || user?.role === "SUPER_ADMIN";
  const dashboard = useQuery({
    queryKey: ["admin-dashboard", period],
    queryFn: () => apiRequest<Dashboard>(`/admin/dashboard/?period=${period}`),
    enabled: Boolean(
      user && allowed && (section === "overview" || section === "analytics"),
    ),
  });
  const resource = resourceFor[section];
  const filterName =
    section === "companies"
      ? "verification_status"
      : resource && !["audit", "plans"].includes(resource)
        ? "status"
        : "";
  const list = useQuery({
    queryKey: ["admin-list", resource, search, statusFilter],
    queryFn: () =>
      apiRequest<Page>(
        `/admin/${resource}/?page_size=20${search ? `&search=${encodeURIComponent(search)}` : ""}${statusFilter && filterName ? `&${filterName}=${encodeURIComponent(statusFilter)}` : ""}`,
      ),
    enabled: Boolean(user && allowed && resource),
  });
  const users = useQuery({
    queryKey: ["admin-users", search],
    queryFn: () =>
      apiRequest<Page>(
        `/admin/users/?page_size=20${search ? `&search=${encodeURIComponent(search)}` : ""}`,
      ),
    enabled: Boolean(
      user && allowed && (section === "users" || section === "teams"),
    ),
  });
  if (!isReady)
    return <div className="app-loading">Préparation de l’administration…</div>;
  if (!user) return <Navigate to="/connexion?next=%2Fadministration" replace />;
  if (!allowed) return <Navigate to="/dashboard" replace />;
  async function signout() {
    await signOut();
    navigate("/");
  }
  async function toggleUser(row: Record<string, unknown>) {
    if (
      !window.confirm(
        `Confirmer ${row.is_active ? "la suspension" : "la réactivation"} de ce compte ?`,
      )
    )
      return;
    await apiRequest(`/admin/users/${row.id}/status/`, {
      method: "POST",
      body: jsonBody({ is_active: !row.is_active }),
    });
    setFeedback("Statut du compte mis à jour et journalisé.");
    await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }
  async function createTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const requester = String(f.get("requester") ?? "");
    const usersData = await apiRequest<Page>(
      `/admin/users/?search=${encodeURIComponent(requester)}`,
    );
    const id = usersData.results[0]?.id;
    if (!id) {
      setFeedback("Demandeur introuvable.");
      return;
    }
    await apiRequest("/admin/support-tickets/", {
      method: "POST",
      body: jsonBody({
        requester: id,
        subject: f.get("subject"),
        description: f.get("description"),
        priority: f.get("priority"),
      }),
    });
    setFeedback("Ticket de support créé et journalisé.");
    event.currentTarget.reset();
    await queryClient.invalidateQueries({
      queryKey: ["admin-list", "support"],
    });
  }
  async function saveSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    let value: unknown;
    try {
      value = JSON.parse(String(f.get("value") ?? "{}"));
    } catch {
      setFeedback("La valeur doit être un JSON valide.");
      return;
    }
    await apiRequest("/admin/settings/", {
      method: "POST",
      body: jsonBody({
        key: f.get("key"),
        description: f.get("description"),
        value,
      }),
    });
    setFeedback("Paramètre non secret enregistré et journalisé.");
    event.currentTarget.reset();
    await queryClient.invalidateQueries({
      queryKey: ["admin-list", "settings"],
    });
  }
  async function sendNotice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const phone = String(f.get("recipient") ?? "");
    const usersData = await apiRequest<Page>(
      `/admin/users/?search=${encodeURIComponent(phone)}`,
    );
    const id = usersData.results[0]?.id;
    if (!id) {
      setFeedback("Destinataire introuvable.");
      return;
    }
    const idempotencyKey =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`;
    await apiRequest("/admin/notifications/send/", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: jsonBody({
        recipients: [id],
        title: f.get("title"),
        body: f.get("body"),
      }),
    });
    setFeedback(
      "Notification in-app créée. Aucun SMS ou e-mail n’a été envoyé.",
    );
    event.currentTarget.reset();
  }
  return (
    <DashboardShell
      user={user}
      breadcrumb="Administration KEMTA"
      active="overview"
      onSignOut={() => void signout()}
    >
      <div className="admin-console">
        <aside
          className="admin-console-nav"
          aria-label="Modules administratifs"
        >
          {sections.map(([key, label, Icon]) => (
            <Link
              key={key}
              to={`/administration/${key}`}
              className={section === key ? "active" : ""}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </aside>
        <main className="admin-console-main">
          <header className="admin-console-head">
            <div>
              <span className="dashboard-eyebrow">
                Administration sécurisée
              </span>
              <h1>{sections.find(([key]) => key === section)?.[1]}</h1>
            </div>
            <GlobalSearch />
          </header>
          {feedback && (
            <p className="admin-feedback">
              <CheckCircle2 size={16} />
              {feedback}
            </p>
          )}
          {(section === "overview" || section === "analytics") && (
            <Overview
              dashboard={dashboard.data}
              period={period}
              setPeriod={setPeriod}
              loading={dashboard.isLoading}
            />
          )}
          {section === "users" && (
            <List
              title="Comptes utilisateurs"
              page={users.data}
              loading={users.isLoading}
              search={search}
              setSearch={setSearch}
              onUserToggle={toggleUser}
              exportHref="/api/v1/admin/export/users/"
            />
          )}
          {resource && section !== "support" && section !== "settings" && (
            <List
              title={sections.find(([key]) => key === section)?.[1] ?? ""}
              page={list.data}
              loading={list.isLoading}
              search={search}
              setSearch={setSearch}
              filterName={filterName}
              statusFilter={statusFilter}
              setStatusFilter={setStatusFilter}
              exportHref={
                ["projects", "missions"].includes(resource)
                  ? `/api/v1/admin/export/${resource}/`
                  : undefined
              }
            />
          )}
          {section === "teams" && (
            <List
              title="Chefs de projet et agents terrain"
              page={users.data}
              loading={users.isLoading}
              search={search}
              setSearch={setSearch}
            />
          )}
          {section === "payments" && (
            <p className="admin-capability-note">
              Les paiements sont affichés en lecture seule. Aucun fournisseur,
              remboursement, facture ou débit n’est simulé.
            </p>
          )}
          {section === "communications" && (
            <section className="admin-card">
              <h2>Envoyer une notification in-app</h2>
              <p>
                Cette action est journalisée. Les canaux SMS et e-mail exigent
                un fournisseur configuré.
              </p>
              <form onSubmit={(e) => void sendNotice(e)} className="admin-form">
                <input
                  name="recipient"
                  required
                  placeholder="Téléphone ou nom du destinataire"
                />
                <input
                  name="title"
                  required
                  maxLength={180}
                  placeholder="Objet"
                />
                <textarea name="body" maxLength={500} placeholder="Message" />
                <button className="button button-primary">
                  Envoyer la notification
                </button>
              </form>
            </section>
          )}
          {section === "support" && (
            <>
              <List
                title="Tickets de support"
                page={list.data}
                loading={list.isLoading}
                search={search}
                setSearch={setSearch}
                filterName="status"
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
              />
              <section className="admin-card">
                <h2>Créer un ticket</h2>
                <form
                  onSubmit={(e) => void createTicket(e)}
                  className="admin-form"
                >
                  <input
                    name="requester"
                    required
                    placeholder="Téléphone ou nom du demandeur"
                  />
                  <input
                    name="subject"
                    required
                    maxLength={180}
                    placeholder="Objet"
                  />
                  <select name="priority" defaultValue="MEDIUM">
                    <option value="LOW">Faible</option>
                    <option value="MEDIUM">Moyenne</option>
                    <option value="HIGH">Élevée</option>
                    <option value="CRITICAL">Critique</option>
                  </select>
                  <textarea
                    name="description"
                    required
                    placeholder="Description de la demande"
                  />
                  <button className="button button-primary">
                    Créer le ticket
                  </button>
                </form>
              </section>
            </>
          )}
          {section === "settings" && (
            <>
              <List
                title="Paramètres non secrets de la plateforme"
                page={list.data}
                loading={list.isLoading}
                search={search}
                setSearch={setSearch}
              />
              {user.role === "SUPER_ADMIN" && (
                <section className="admin-card">
                  <h2>Ajouter un paramètre non secret</h2>
                  <p>
                    Les jetons, mots de passe et clés fournisseur doivent rester
                    dans la configuration de déploiement.
                  </p>
                  <form
                    onSubmit={(e) => void saveSetting(e)}
                    className="admin-form"
                  >
                    <input
                      name="key"
                      required
                      maxLength={80}
                      placeholder="Clé, par exemple maintenance_banner"
                    />
                    <input
                      name="description"
                      maxLength={300}
                      placeholder="Description"
                    />
                    <textarea
                      name="value"
                      required
                      defaultValue="{}"
                      placeholder="Valeur JSON"
                    />
                    <button className="button button-primary">
                      Enregistrer
                    </button>
                  </form>
                </section>
              )}
            </>
          )}
        </main>
      </div>
    </DashboardShell>
  );
}
function Overview({
  dashboard,
  period,
  setPeriod,
  loading,
}: {
  dashboard: Dashboard | undefined;
  period: string;
  setPeriod: (v: string) => void;
  loading: boolean;
}) {
  if (loading || !dashboard)
    return (
      <div className="dashboard-skeleton">
        <div />
        <div />
        <div />
      </div>
    );
  const s = dashboard.statistics;
  const metrics = [
    ["Utilisateurs", s.users_total],
    ["Comptes actifs", s.users_active],
    ["Entreprises à vérifier", s.companies_pending],
    ["Projets actifs", s.projects_active],
    ["Demandes en attente", s.requests_pending],
    ["Missions en cours", s.missions_in_progress],
    ["Rapports à examiner", s.reports_to_review],
    ["Incidents critiques", s.issues_critical],
    ["Paiements à rapprocher", s.payments_pending],
    ["Abonnements actifs", s.subscriptions_active],
  ];
  const max = Math.max(
    1,
    ...dashboard.series.map((x) => Math.max(x.users, x.projects, x.requests)),
  );
  return (
    <>
      <section className="admin-period">
        <label>
          Période{" "}
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="1">Aujourd’hui</option>
            <option value="7">7 jours</option>
            <option value="30">30 jours</option>
            <option value="90">90 jours</option>
          </select>
        </label>
        <span>
          Données agrégées côté serveur · {dashboard.period_days} jour(s)
        </span>
      </section>
      <div className="admin-kpis">
        {metrics.map(([l, v]) => (
          <div key={String(l)}>
            <small>{l}</small>
            <strong>{String(v ?? 0)}</strong>
          </div>
        ))}
      </div>
      <section className="admin-card">
        <h2>Évolution des inscriptions, projets et demandes</h2>
        <div className="admin-chart" aria-label="Graphique des activités">
          <div>
            {dashboard.series.map((point) => (
              <span
                key={point.date}
                title={`${point.date}: ${point.users} inscriptions, ${point.projects} projets, ${point.requests} demandes`}
                style={{
                  height: `${Math.max(4, (Math.max(point.users, point.projects, point.requests) / max) * 100)}%`,
                }}
              />
            ))}
          </div>
        </div>
      </section>
      <section className="admin-card">
        <h2>Centre d’alertes</h2>
        {dashboard.alerts.length ? (
          <div className="admin-alerts">
            {dashboard.alerts.map((a, i) => (
              <Link
                to={a.href}
                key={`${a.type}-${i}`}
                className={`severity-${a.severity.toLowerCase()}`}
              >
                <AlertTriangle size={17} />
                <span>
                  <strong>{a.title}</strong>
                  <small>{a.detail}</small>
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <p>Aucune alerte nécessitant une intervention immédiate.</p>
        )}
      </section>
    </>
  );
}
function List({
  title,
  page,
  loading,
  search,
  setSearch,
  onUserToggle,
  exportHref,
  filterName,
  statusFilter,
  setStatusFilter,
}: {
  title: string;
  page: Page | undefined;
  loading: boolean;
  search: string;
  setSearch: (v: string) => void;
  onUserToggle?: (x: Record<string, unknown>) => void;
  exportHref?: string | undefined;
  filterName?: string | undefined;
  statusFilter?: string | undefined;
  setStatusFilter?: ((v: string) => void) | undefined;
}) {
  const rows = page?.results ?? [];
  return (
    <section className="admin-card">
      <div className="admin-list-head">
        <h2>{title}</h2>
        {exportHref && (
          <a className="subtle-button" href={exportHref}>
            <Download size={15} /> CSV
          </a>
        )}
      </div>
      <div className="admin-list-filters">
        <input
          className="admin-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher côté serveur…"
        />
        {filterName && setStatusFilter && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label={`Filtrer par ${filterName}`}
          >
            <option value="">Tous les statuts</option>
            <option value="NEW">Nouveau</option>
            <option value="PENDING">En attente</option>
            <option value="IN_PROGRESS">En cours</option>
            <option value="ACTIVE">Actif</option>
            <option value="COMPLETED">Terminé</option>
            <option value="RESOLVED">Résolu</option>
            <option value="CLOSED">Clos</option>
            <option value="FAILED">Échoué</option>
          </select>
        )}
      </div>
      {loading ? (
        <p>Chargement…</p>
      ) : rows.length ? (
        <div className="admin-table">
          <table>
            <thead>
              <tr>
                {Object.keys(rows[0]!)
                  .filter((k) => !["messages", "metadata", "value"].includes(k))
                  .slice(0, 8)
                  .map((k) => (
                    <th key={k}>{k.replaceAll("_", " ")}</th>
                  ))}
                {onUserToggle && <th>action</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.id)}>
                  {Object.keys(rows[0]!)
                    .filter(
                      (k) => !["messages", "metadata", "value"].includes(k),
                    )
                    .slice(0, 8)
                    .map((k) => (
                      <td key={k}>
                        {typeof row[k] === "object"
                          ? "—"
                          : String(row[k] ?? "—")}
                      </td>
                    ))}
                  {onUserToggle && (
                    <td>
                      <button
                        className="subtle-button"
                        onClick={() => void onUserToggle(row)}
                      >
                        {row.is_active ? "Suspendre" : "Réactiver"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Aucune donnée ne correspond aux filtres.</p>
      )}
    </section>
  );
}
function GlobalSearch() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<
    Array<{ label: string; meta: string; href: string }>
  >([]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    const r = await apiRequest<{
      results: Array<{ label: string; meta: string; href: string }>;
    }>(`/admin/search/?q=${encodeURIComponent(q)}`);
    setItems(r.results);
  }
  return (
    <form className="admin-global-search" onSubmit={(e) => void submit(e)}>
      <Search size={16} />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Recherche globale"
      />
      <button aria-label="Rechercher">Rechercher</button>
      {items.length > 0 && (
        <div>
          {items.map((i, n) => (
            <Link key={n} to={i.href} onClick={() => setItems([])}>
              <strong>{i.label}</strong>
              <small>{i.meta}</small>
            </Link>
          ))}
        </div>
      )}
    </form>
  );
}
