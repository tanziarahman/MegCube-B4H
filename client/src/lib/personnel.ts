export interface PersonnelGroup {
  group_id: string;
  group_name: string;
}

export interface PersonnelRecord {
  person_id: string;
  face_image1?: string;
  groups?: PersonnelGroup[];
  person_info?: {
    name?: string;
    code?: string;
    birthday?: string;
    remarks?: string;
  };
}

export interface PersonnelPage {
  total_count: number;
  person_list: PersonnelRecord[];
}

function extractUri(val: unknown): string | undefined {
  if (!val) return undefined;
  if (typeof val === 'string') return val;
  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>;
    const uri = obj.image_uri ?? obj.uri ?? obj.url ?? obj.value ?? obj.image_data;
    if (typeof uri === 'string') return uri;
  }
  if (Array.isArray(val) && val.length > 0) {
    return extractUri(val[0]);
  }
  return undefined;
}

const imageUrl = (uri?: string, cacheKey?: string) =>
  uri ? `/api/image?uri=${encodeURIComponent(uri)}&v=${encodeURIComponent(cacheKey ?? uri)}` : undefined;

export async function fetchPersonnel(page: number, size = 10): Promise<PersonnelPage> {
  const res = await fetch(`/api/personnel?page=${page}&size=${size}&get_feature=true`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Could not load personnel (${res.status})`);
  const data = (await res.json()) as PersonnelPage;
  return {
    total_count: Number(data.total_count ?? 0),
    person_list: (data.person_list ?? []).map((person) => {
      const pObj = (person as unknown) as Record<string, unknown>;
      const rawImg = person.face_image1 ?? pObj.face_image ?? pObj.face_data ?? pObj.image_data;
      const uri = extractUri(rawImg);
      return {
        ...person,
        face_image1: imageUrl(uri, person.person_id),
      };
    }),
  };
}

export async function fetchPersonnelGroups(): Promise<PersonnelGroup[]> {
  const res = await fetch('/api/personnel/groups', { cache: 'no-store' });
  if (!res.ok) throw new Error(`Could not load groups (${res.status})`);
  return ((await res.json()) as { groups?: PersonnelGroup[] }).groups ?? [];
}

export async function createPersonnel(form: FormData): Promise<void> {
  const res = await fetch('/api/personnel', { method: 'POST', body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Could not add person (${res.status})`);
}

export async function deletePersonnel(id: string): Promise<void> {
  const res = await fetch(`/api/personnel/${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Could not delete person (${res.status})`);
}

export async function updatePersonnel(id: string, form: FormData): Promise<void> {
  const res = await fetch(`/api/personnel/${encodeURIComponent(id)}`, { method: 'PUT', body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Could not update person (${res.status})`);
}