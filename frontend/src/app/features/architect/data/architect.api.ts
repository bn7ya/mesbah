import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { map, type Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import { blueprintOf, designRequest } from './blueprint';
import {
  DATASET_READY,
  DEFAULT_BATCH,
  DEFAULT_SEQ_LEN,
  type Blueprint,
  type DatasetOption,
  type DatasetWire,
  type Draft,
  type DraftChangeWire,
  type DraftText,
  type DraftWire,
  type Estimate,
  type EstimateRequest,
  type NewDraftWire,
  type PlanWire,
  type Preset,
  type PresetListWire,
  type PresetWire,
  type ProjectRef,
  type TrainRequest,
  type TrainStarted,
} from './architect.types';

function presetOf(wire: PresetWire): Preset {
  return {
    name: wire.name,
    family: wire.design.family,
    counts: wire.counts,
    blueprint: blueprintOf(wire.design, { tokenizer: '', seq_len: DEFAULT_SEQ_LEN, batch: DEFAULT_BATCH }),
  };
}

function draftOf(wire: DraftWire): Draft {
  return {
    id: wire.id,
    name: wire.name,
    notes: wire.notes,
    family: wire.design.family,
    counts: wire.counts,
    updatedAt: wire.updated_at,
    createdBy: wire.created_by,
    blueprint: blueprintOf(wire.design, { tokenizer: wire.tokenizer, seq_len: wire.seq_len, batch: wire.batch }),
  };
}

@Injectable({ providedIn: 'root' })
export class ArchitectApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/architect';

  presets(): Observable<readonly Preset[]> {
    return this.http.get<PresetListWire>(`${this.base}/presets/`).pipe(map((list) => list.presets.map(presetOf)));
  }

  estimate(request: EstimateRequest): Observable<Estimate> {
    return this.http.post<Estimate>(`${this.base}/estimate/`, request);
  }

  drafts(query: PageQuery): Observable<Page<Draft>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http
      .get<Page<DraftWire>>(`${this.base}/drafts/`, { params })
      .pipe(map((page) => ({ ...page, results: page.results.map(draftOf) })));
  }

  createDraft(text: DraftText, blueprint: Blueprint): Observable<Draft> {
    const body: NewDraftWire = {
      ...text,
      design: designRequest(blueprint),
      tokenizer: blueprint.tokenizer.trim(),
      seq_len: blueprint.seq_len ?? undefined,
      batch: blueprint.batch ?? undefined,
    };
    return this.http.post<DraftWire>(`${this.base}/drafts/`, body).pipe(map(draftOf));
  }

  changeDraft(id: string, text: DraftText, blueprint: Blueprint | null): Observable<Draft> {
    const body: DraftChangeWire =
      blueprint === null
        ? text
        : {
            ...text,
            design: designRequest(blueprint),
            tokenizer: blueprint.tokenizer.trim(),
            seq_len: blueprint.seq_len ?? undefined,
            batch: blueprint.batch ?? undefined,
          };
    return this.http.patch<DraftWire>(`${this.base}/drafts/${id}/`, body).pipe(map(draftOf));
  }

  removeDraft(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/drafts/${id}/`);
  }

  train(id: string, request: TrainRequest): Observable<TrainStarted> {
    return this.http.post<TrainStarted>(`${this.base}/drafts/${id}/train/`, request);
  }

  projects(pageSize: number): Observable<readonly ProjectRef[]> {
    const params = new HttpParams({ fromObject: { page_size: pageSize } });
    return this.http
      .get<Page<ProjectRef>>('/api/projects/', { params })
      .pipe(map((page) => page.results.map(({ id, name }) => ({ id, name }))));
  }

  datasets(pageSize: number): Observable<readonly DatasetOption[]> {
    const params = new HttpParams({ fromObject: { page_size: pageSize } });
    return this.http.get<Page<DatasetWire>>('/api/datasets/', { params }).pipe(
      map((page) =>
        page.results
          .filter((dataset) => dataset.status === DATASET_READY)
          .map(({ id, name, rows, has_thinking }) => ({ id, name, rows, hasThinking: has_thinking })),
      ),
    );
  }

  corrections(projectId: string): Observable<number> {
    const params = new HttpParams({ fromObject: { project: projectId } });
    return this.http.get<PlanWire>('/api/training/plan/', { params }).pipe(map((plan) => plan.corrections));
  }
}
