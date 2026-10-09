import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useParams } from 'react-router-dom';
import { AlertTriangle, Camera, CheckCircle2, ClipboardCheck, MapPin, Play, Send } from 'lucide-react';
import { ApiError, apiRequest, jsonBody } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { flushOutbox, queueFile, queueJson } from './offlineOutbox';

type Mission = { id: number; project: number; project_name: string; assigned_to: number; assigned_to_name: string; title: string; description: string; status: string; status_label: string; mission_type_label: string; scheduled_start: string | null; location: string; checklist: Checklist[]; requires_geo_confirmation: boolean; revision_reason: string; report_status: string | null };
type Checklist = { id: string; label: string; required?: boolean; completed?: boolean };
type Report = { id: number; mission: number; mission_title: string; summary: string; observations: string; progress_percentage: number; checklist_results: Checklist[]; status: string; status_label: string; review_comment: string };
type Assignment = { id: number; project: number; project_name: string; user: number; user_name: string; status: string };
type Issue = { id: number; title: string; description: string; priority: string; status: string; status_label: string };
type Operations = { role: string; statistics: Record<string, number>; today_missions: Mission[]; upcoming_missions?: Mission[]; missions_in_progress?: Mission[]; reports_to_review?: Report[]; reports_to_correct?: Report[]; open_issues?: Issue[]; my_open_issues?: Issue[]; assignments?: Assignment[] };

const statusClass = (value: string) => `field-status field-status-${value.toLowerCase().replaceAll('_', '-')}`;
const missionDate = (value: string | null) => value ? new Intl.DateTimeFormat('fr-CM', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'À programmer';

function useOperations() {
  return useQuery({ queryKey: ['field-operations'], queryFn: () => apiRequest<Operations>('/dashboard/field-operations/'), staleTime: 30_000 });
}

export function FieldOperationsDashboard({ manager }: { manager: boolean }) {
  const operations = useOperations();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [notice, setNotice] = useState('');
  const [plannerOpen, setPlannerOpen] = useState(false);

  useEffect(() => {
    const sync = async () => {
      const count = await flushOutbox().catch(() => 0);
      if (count) { setNotice(`${count} action${count > 1 ? 's' : ''} terrain synchronisée${count > 1 ? 's' : ''}.`); void queryClient.invalidateQueries({ queryKey: ['field-operations'] }); }
    };
    void sync();
    window.addEventListener('online', sync);
    return () => window.removeEventListener('online', sync);
  }, [queryClient]);

  if (operations.isLoading) return <div className="field-loading">Chargement des opérations terrain…</div>;
  if (operations.isError) return <div className="dashboard-error"><AlertTriangle size={20} /><div><strong>Les opérations terrain ne sont pas disponibles.</strong><p>{operations.error instanceof ApiError ? operations.error.message : 'Réessayez dès que la connexion est rétablie.'}</p></div></div>;
  const data = operations.data!;
  if (manager && data.role !== 'PROJECT_MANAGER') return null;
  if (!manager && data.role !== 'FIELD_AGENT') return null;

  async function review(report: Report, action: 'start-review' | 'approve' | 'request-revision') {
    const reason = action === 'request-revision' ? window.prompt('Précisez la correction demandée :') : undefined;
    if (action === 'request-revision' && !reason) return;
    await apiRequest(`/field-reports/${report.id}/${action}/`, { method: 'POST', body: jsonBody(reason ? { reason } : {}) });
    setNotice(action === 'approve' ? 'Rapport validé et agent notifié.' : 'La revue a été mise à jour.');
    await queryClient.invalidateQueries({ queryKey: ['field-operations'] });
  }

  return <section className="field-operations">
    <div className="field-ops-intro">
      <div><span className="dashboard-eyebrow">{manager ? 'Pilotage opérationnel' : 'Terrain · mes missions'}</span><h2>{manager ? 'Décider à partir des constats terrain' : 'Vos visites, même quand le réseau est faible'}</h2><p>{manager ? 'Planifiez, affectez, consultez les preuves et contrôlez chaque rapport avant validation.' : 'Les actions sont enregistrées avec une référence unique et seront synchronisées au retour de connexion.'}</p></div>
      {manager && <button className="button button-primary" onClick={() => setPlannerOpen((value) => !value)}>Planifier une mission</button>}
    </div>
    {notice && <div className="field-notice"><CheckCircle2 size={17} /> {notice}</div>}
    <div className="field-kpis">
      {Object.entries(data.statistics).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{labelFor(key)}</span></div>)}
    </div>
    {manager && plannerOpen && <MissionPlanner assignments={data.assignments ?? []} onDone={async () => { setPlannerOpen(false); setNotice('Mission planifiée et agent notifié.'); await queryClient.invalidateQueries({ queryKey: ['field-operations'] }); }} />}
    {manager ? <>
      <MissionList title="Aujourd’hui" missions={data.today_missions} empty="Aucune mission prévue aujourd’hui." />
      <section className="field-section"><div className="field-section-heading"><span>Rapports à contrôler</span><strong>{data.reports_to_review?.length ?? 0}</strong></div>{data.reports_to_review?.length ? <div className="field-report-list">{data.reports_to_review.map((report) => <article key={report.id} className="field-report-card"><div><strong>{report.mission_title}</strong><p>{report.summary}</p><span className={statusClass(report.status)}>{report.status_label}</span></div><div className="field-report-actions">{report.status === 'SUBMITTED' && <button onClick={() => void review(report, 'start-review')}>Prendre en revue</button>}<button className="button button-primary button-small" onClick={() => void review(report, 'approve')}>Valider</button><button className="button button-outline button-small" onClick={() => void review(report, 'request-revision')}>Correction</button></div></article>)}</div> : <Empty text="Aucun rapport en attente de validation." />}</section>
      <IssueList issues={data.open_issues ?? []} />
    </> : <>
      <MissionList title="À faire aujourd’hui" missions={data.today_missions} empty="Aucune mission à traiter aujourd’hui." />
      <MissionList title="À venir" missions={data.upcoming_missions ?? []} empty="Aucune mission planifiée ensuite." />
      {(data.reports_to_correct?.length ?? 0) > 0 && <section className="field-section"><div className="field-section-heading"><span>Rapports à corriger</span></div>{data.reports_to_correct!.map((report) => <Link className="field-revision" key={report.id} to={`/missions/${report.mission}`}><AlertTriangle size={18} /><span><strong>{report.mission_title}</strong><small>{report.review_comment}</small></span></Link>)}</section>}
      <IssueList issues={data.my_open_issues ?? []} />
    </>}
    {!navigator.onLine && <div className="field-offline"><span /> Hors connexion : les saisies et médias restent dans la file locale jusqu’au prochain réseau.</div>}
    {user?.email?.endsWith('@kemta.invalid') && <p className="field-demo-note">DÉMO — les missions affichées sont fictives et servent uniquement à présenter le workflow KEMTA.</p>}
  </section>;
}

function MissionPlanner({ assignments, onDone }: { assignments: Assignment[]; onDone: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const active = assignments.filter((item) => item.status === 'ACTIVE');
  const projects = Array.from(new Map(active.map((item) => [item.project, item.project_name])).entries());
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setSaving(true);
    try { await apiRequest('/field-missions/', { method: 'POST', body: jsonBody({ project: Number(form.get('project')), assigned_to: Number(form.get('agent')), title: form.get('title'), description: form.get('description'), location: form.get('location'), scheduled_start: form.get('scheduled_start') || null, checklist: [{ id: 'observation', label: 'Consigner l’observation terrain', required: true }] }) }); await onDone(); } finally { setSaving(false); }
  }
  return <form className="field-planner" onSubmit={(event) => void submit(event)}><label>Projet<select name="project" required><option value="">Choisir</option>{projects.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Agent<select name="agent" required><option value="">Choisir</option>{active.map((item) => <option key={item.id} value={item.user}>{item.user_name} · {item.project_name}</option>)}</select></label><label>Mission<input name="title" required placeholder="Ex. Contrôle bétonnage" /></label><label>Créneau<input name="scheduled_start" type="datetime-local" /></label><label className="field-wide">Instructions<textarea name="description" rows={2} placeholder="Ce qui doit être observé et documenté" /></label><label className="field-wide">Lieu<input name="location" placeholder="Quartier / chantier" /></label><button className="button button-primary" disabled={saving}>{saving ? 'Planification…' : 'Créer et affecter'}</button></form>;
}

function MissionList({ title, missions, empty }: { title: string; missions: Mission[]; empty: string }) { return <section className="field-section"><div className="field-section-heading"><span>{title}</span><strong>{missions.length}</strong></div>{missions.length ? <div className="mission-list">{missions.map((mission) => <Link className="mission-card" to={`/missions/${mission!.id}`} key={mission!.id}><div><span className={statusClass(mission!.status)}>{mission!.status_label}</span><h3>{mission!.title}</h3><p>{mission!.project_name}</p><small><MapPin size={14} /> {mission!.location || 'Lieu à confirmer'} · {missionDate(mission!.scheduled_start)}</small></div><ClipboardCheck size={22} /></Link>)}</div> : <Empty text={empty} />}</section>; }
function IssueList({ issues }: { issues: Issue[] }) { return <section className="field-section"><div className="field-section-heading"><span>Problèmes ouverts</span><strong>{issues.length}</strong></div>{issues.length ? <div className="field-issue-list">{issues.map((issue) => <div key={issue.id}><AlertTriangle size={18} /><span><strong>{issue.title}</strong><small>{issue.description}</small></span><b>{issue.status_label}</b></div>)}</div> : <Empty text="Aucun problème ouvert." />}</section>; }
function Empty({ text }: { text: string }) { return <div className="field-empty">{text}</div>; }
function labelFor(key: string) { return ({ active_projects: 'projets actifs', missions_today: 'missions du jour', missions_in_progress: 'missions actives', reports_to_review: 'rapports à revoir', open_issues: 'problèmes ouverts', in_progress: 'en cours', awaiting_correction: 'à corriger' } as Record<string, string>)[key] ?? key.replaceAll('_', ' '); }

export function MissionDetailPage() {
  const { missionId } = useParams(); const id = Number(missionId); const { user, isReady } = useAuth(); const queryClient = useQueryClient();
  const missionQuery = useQuery({ queryKey: ['mission', id], queryFn: () => apiRequest<Mission>(`/field-missions/${id}/`), enabled: Boolean(id && user) });
  const reportQuery = useQuery({ queryKey: ['mission-report', id], queryFn: async () => { const data = await apiRequest<{ results: Report[] }>(`/field-reports/?mission=${id}`); return data.results[0] ?? null; }, enabled: Boolean(id && user) });
  const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false); const submitMode = useRef(false);
  const mission = missionQuery.data; const report = reportQuery.data;
  const checks = useMemo(() => (report?.checklist_results?.length ? report.checklist_results : mission?.checklist.map((item) => ({ ...item, completed: false })) ?? []), [mission, report]);
  const [results, setResults] = useState<Checklist[]>([]);
  useEffect(() => setResults(checks), [checks]);
  if (!isReady) return null; if (!user) return <Navigate to="/connexion?next=%2Fdashboard" replace />; if (missionQuery.isLoading) return <main className="mission-page">Chargement de la mission…</main>; if (!mission) return <main className="mission-page">Mission indisponible.</main>;
  async function action(path: string, body: Record<string, unknown> = {}) { setBusy(true); try { await apiRequest(`/field-missions/${id}/${path}/`, { method: 'POST', body: jsonBody(body) }); setMessage('Mission mise à jour.'); await queryClient.invalidateQueries({ queryKey: ['mission', id] }); await queryClient.invalidateQueries({ queryKey: ['field-operations'] }); } finally { setBusy(false); } }
  async function start() { let point: Record<string, unknown> = {}; if (mission!.requires_geo_confirmation && 'geolocation' in navigator) { const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: false, timeout: 8000 })); point = { latitude: position.coords.latitude, longitude: position.coords.longitude }; } await action('start', point); }
  async function saveReport(event: FormEvent<HTMLFormElement>, submit = false) { event.preventDefault(); const form = new FormData(event.currentTarget); const payload = { mission: id, summary: form.get('summary'), observations: form.get('observations'), progress_percentage: Number(form.get('progress_percentage')), checklist_results: results }; try { let current = report; if (!current) current = await apiRequest<Report>('/field-reports/', { method: 'POST', body: jsonBody(payload), headers: { 'Idempotency-Key': crypto.randomUUID() } }); else current = await apiRequest<Report>(`/field-reports/${current.id}/`, { method: 'PATCH', body: jsonBody(payload) }); if (submit) await apiRequest(`/field-reports/${current.id}/submit/`, { method: 'POST', body: jsonBody({}) }); setMessage(submit ? 'Rapport envoyé au Chef de Projet.' : 'Brouillon enregistré.'); await queryClient.invalidateQueries({ queryKey: ['mission-report', id] }); await queryClient.invalidateQueries({ queryKey: ['mission', id] }); } catch { if (report) { await queueJson(`/field-reports/${report.id}/`, 'PATCH', payload); if (submit) await queueJson(`/field-reports/${report.id}/submit/`, 'POST', {}); } else { await queueJson('/field-reports/', 'POST', payload, submit ? '/field-reports/:id/submit/' : undefined); } setMessage('Connexion absente : le rapport est dans la file de synchronisation.'); } }
  async function upload(file: File) { const data = new FormData(); const video = file.type.startsWith('video/'); data.append('project', String(mission!.project)); data.append('mission', String(id)); data.append('title', `Preuve ${video ? 'vidéo' : 'photo'} · ${mission!.title}`); data.append('evidence_type', video ? 'VIDEO' : 'PHOTO'); data.append(video ? 'video' : 'image', file); data.append('client_reference', crypto.randomUUID()); try { await apiRequest('/evidences/', { method: 'POST', body: data }); setMessage('Preuve ajoutée.'); } catch { await queueFile('/evidences/', { project: String(mission!.project), mission: String(id), title: `Preuve ${video ? 'vidéo' : 'photo'} · ${mission!.title}`, evidence_type: video ? 'VIDEO' : 'PHOTO' }, file, video ? 'video' : 'image'); setMessage('Preuve mise en attente de synchronisation.'); } }
  async function issue(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const f = new FormData(event.currentTarget); const payload = { project: mission!.project, mission: id, title: f.get('title'), description: f.get('description'), priority: f.get('priority'), client_reference: crypto.randomUUID() }; try { await apiRequest('/project-issues/', { method: 'POST', body: jsonBody(payload) }); setMessage('Problème signalé au Chef de Projet.'); } catch { await queueJson('/project-issues/', 'POST', payload); setMessage('Problème conservé dans la file hors connexion.'); } }
  return <main className="mission-page"><Link to="/dashboard" className="text-link">← Retour aux missions</Link><header><span className={statusClass(mission!.status)}>{mission!.status_label}</span><h1>{mission!.title}</h1><p>{mission!.project_name} · {mission!.location || 'Lieu à confirmer'}</p>{mission!.revision_reason && <div className="field-revision"><AlertTriangle size={18} /><span><strong>Correction demandée</strong><small>{mission!.revision_reason}</small></span></div>}</header>{message && <div className="field-notice"><CheckCircle2 size={17} /> {message}</div>}<section className="mission-action-bar">{mission!.status === 'PLANNED' && <button className="button button-primary" disabled={busy} onClick={() => void action('accept')}>Accepter la mission</button>}{['ACCEPTED', 'REVISION_REQUIRED'].includes(mission!.status) && <button className="button button-primary" disabled={busy} onClick={() => void start()}><Play size={17} /> Démarrer la visite</button>}{mission!.status === 'IN_PROGRESS' && <label className="button button-outline"><Camera size={17} /> Photo / vidéo<input hidden type="file" accept="image/*,video/mp4,video/webm,video/quicktime" capture="environment" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} /></label>}</section><section className="mission-form-card"><h2><ClipboardCheck size={20} /> Checklist et rapport</h2><form onSubmit={(event) => void saveReport(event, submitMode.current)}>{results.map((item, index) => <label className="check-row" key={item.id}><input type="checkbox" checked={Boolean(item.completed)} onChange={(event) => setResults((value) => value.map((row, rowIndex) => rowIndex === index ? { ...row, completed: event.target.checked } : row))} /><span>{item.label}{item.required && ' · requis'}</span></label>)}<label>Résumé<textarea name="summary" required defaultValue={report?.summary} placeholder="Ce que vous avez constaté" /></label><label>Observations<textarea name="observations" defaultValue={report?.observations} placeholder="Mesures, risques ou éléments à suivre" /></label><label>Avancement (%)<input name="progress_percentage" type="number" min="0" max="100" defaultValue={report?.progress_percentage ?? 0} /></label>{mission!.status === 'IN_PROGRESS' && <div className="mission-submit-actions"><button type="submit" className="button button-outline" onClick={() => { submitMode.current = false; }}>Enregistrer le brouillon</button><button type="submit" className="button button-primary" onClick={() => { submitMode.current = true; }}><Send size={16} /> Soumettre au Chef</button></div>}</form></section>{mission!.status === 'IN_PROGRESS' && <section className="mission-form-card"><h2><AlertTriangle size={20} /> Signaler un problème</h2><form onSubmit={(event) => void issue(event)} className="issue-form"><input name="title" required placeholder="Titre court" /><select name="priority"><option value="MEDIUM">Priorité moyenne</option><option value="HIGH">Priorité élevée</option><option value="CRITICAL">Critique</option></select><textarea name="description" required placeholder="Décrivez le problème et son emplacement" /><button className="button button-outline">Envoyer le signalement</button></form></section>}<p className="field-privacy"><MapPin size={15} /> KEMTA ne suit jamais votre position en continu. La position n’est demandée qu’au démarrage lorsque cette mission le requiert.</p></main>;
}
