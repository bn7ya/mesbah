import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ChatMessage, ChatSession, CuratedModel, ModelVersion, Project,
  SystemInfo, Task, TrainingRun, VersionNode,
} from './types';

/** Base URL of the FastAPI backend. Same host in dev via proxy; override for prod. */
export const API_BASE = '/api';
/** WebSocket origin for live training metrics. */
export const WS_BASE =
  (typeof location !== 'undefined' ? location.origin.replace(/^http/, 'ws') : 'ws://localhost:4200');

/**
 * Single typed gateway to the backend. Kept as one service (the surface is
 * small and cohesive); feature components inject just this.
 */
@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);

  // ── system ──
  system(): Observable<SystemInfo> { return this.http.get<SystemInfo>(`${API_BASE}/system`); }

  // ── projects ──
  listProjects(): Observable<Project[]> { return this.http.get<Project[]>(`${API_BASE}/projects`); }
  getProject(id: string): Observable<Project> { return this.http.get<Project>(`${API_BASE}/projects/${id}`); }
  createProject(body: Partial<Project> & { base_model_repo: string; name: string }): Observable<Project> {
    return this.http.post<Project>(`${API_BASE}/projects`, body);
  }
  updateProject(id: string, body: Partial<Project>): Observable<Project> {
    return this.http.patch<Project>(`${API_BASE}/projects/${id}`, body);
  }
  deleteProject(id: string): Observable<void> { return this.http.delete<void>(`${API_BASE}/projects/${id}`); }

  // ── models ──
  curatedModels(): Observable<CuratedModel[]> { return this.http.get<CuratedModel[]>(`${API_BASE}/models/curated`); }
  searchModels(q: string): Observable<any[]> { return this.http.get<any[]>(`${API_BASE}/models/search`, { params: { query: q } }); }
  localModels(): Observable<any[]> { return this.http.get<any[]>(`${API_BASE}/models/local`); }
  downloadModel(repo_id: string): Observable<any> { return this.http.post(`${API_BASE}/models/download`, { repo_id }); }
  downloadStatus(repo_id: string): Observable<any> { return this.http.get(`${API_BASE}/models/download/status`, { params: { repo_id } }); }

  // ── tasks ──
  listTasks(pid: string): Observable<Task[]> { return this.http.get<Task[]>(`${API_BASE}/projects/${pid}/tasks`); }
  createTask(pid: string, body: Partial<Task>): Observable<Task> { return this.http.post<Task>(`${API_BASE}/projects/${pid}/tasks`, body); }
  updateTask(pid: string, id: string, body: Partial<Task>): Observable<Task> { return this.http.patch<Task>(`${API_BASE}/projects/${pid}/tasks/${id}`, body); }
  deleteTask(pid: string, id: string): Observable<void> { return this.http.delete<void>(`${API_BASE}/projects/${pid}/tasks/${id}`); }

  // ── sessions / chat ──
  listSessions(pid: string): Observable<ChatSession[]> { return this.http.get<ChatSession[]>(`${API_BASE}/projects/${pid}/sessions`); }
  createSession(pid: string, body: Partial<ChatSession>): Observable<ChatSession> { return this.http.post<ChatSession>(`${API_BASE}/projects/${pid}/sessions`, body); }
  getSession(id: string): Observable<ChatSession> { return this.http.get<ChatSession>(`${API_BASE}/sessions/${id}`); }
  updateSession(id: string, body: Partial<ChatSession>): Observable<ChatSession> { return this.http.patch<ChatSession>(`${API_BASE}/sessions/${id}`, body); }
  deleteSession(id: string): Observable<void> { return this.http.delete<void>(`${API_BASE}/sessions/${id}`); }
  chat(sessionId: string, content: string, opts: Record<string, unknown> = {}): Observable<ChatMessage[]> {
    return this.http.post<ChatMessage[]>(`${API_BASE}/sessions/${sessionId}/chat`, { content, ...opts });
  }
  regenerate(sessionId: string): Observable<ChatMessage> { return this.http.post<ChatMessage>(`${API_BASE}/sessions/${sessionId}/regenerate`, {}); }
  editMessage(id: string, body: { content?: string; approved?: boolean; include_in_training?: boolean }): Observable<ChatMessage> {
    return this.http.patch<ChatMessage>(`${API_BASE}/messages/${id}`, body);
  }
  deleteMessage(id: string): Observable<void> { return this.http.delete<void>(`${API_BASE}/messages/${id}`); }

  // ── training ──
  datasetPreview(pid: string): Observable<{ count: number; sample: any[] }> {
    return this.http.get<{ count: number; sample: any[] }>(`${API_BASE}/projects/${pid}/training/preview`);
  }
  listRuns(pid: string): Observable<TrainingRun[]> { return this.http.get<TrainingRun[]>(`${API_BASE}/projects/${pid}/training/runs`); }
  createRun(pid: string, body: Record<string, unknown>): Observable<TrainingRun> { return this.http.post<TrainingRun>(`${API_BASE}/projects/${pid}/training/runs`, body); }
  getRun(id: string): Observable<TrainingRun> { return this.http.get<TrainingRun>(`${API_BASE}/training/runs/${id}`); }
  cancelRun(id: string): Observable<{ cancelled: boolean }> { return this.http.post<{ cancelled: boolean }>(`${API_BASE}/training/runs/${id}/cancel`, {}); }

  // ── versioning ──
  versionTree(pid: string): Observable<VersionNode[]> { return this.http.get<VersionNode[]>(`${API_BASE}/projects/${pid}/version-tree`); }
  listVersions(pid: string): Observable<ModelVersion[]> { return this.http.get<ModelVersion[]>(`${API_BASE}/projects/${pid}/versions`); }
  activateVersion(pid: string, vid: string): Observable<ModelVersion> { return this.http.post<ModelVersion>(`${API_BASE}/projects/${pid}/versions/${vid}/activate`, {}); }
  updateVersion(vid: string, body: { label?: string; notes?: string }): Observable<ModelVersion> { return this.http.patch<ModelVersion>(`${API_BASE}/versions/${vid}`, body); }
  deleteVersion(vid: string): Observable<void> { return this.http.delete<void>(`${API_BASE}/versions/${vid}`); }

  /** Live training metrics WebSocket for a run. */
  trainingSocket(runId: string): WebSocket {
    return new WebSocket(`${WS_BASE}/api/training/runs/${runId}/ws`);
  }
}
