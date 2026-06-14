import { createClient } from './client'
import type {
  LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, AccessTokenResponse, User,
  ChatRequest, ChatAccepted, StreamTicket, CancelResponse,
  SessionList, SessionDetail, GroupList, Group, CreateGroupRequest, GroupPreferences,
  PlanList, Plan, PlanMap, PlanCalendar, ModifyRequest, ModifyAccepted,
} from './types'

let tokenGetter: () => string | null = () => null
export function setTokenGetter(fn: () => string | null) { tokenGetter = fn }

export const client = createClient({ baseUrl: import.meta.env.VITE_API_BASE || '/api/v1', getToken: () => tokenGetter() })

export const api = {
  // Auth
  register: (b: RegisterRequest) => client.post<RegisterResponse>('/auth/register', b),
  login: (b: LoginRequest) => client.post<LoginResponse>('/auth/login', b),
  refresh: (refresh_token: string) => client.post<AccessTokenResponse>('/auth/refresh', { refresh_token }),
  logout: (refresh_token: string) => client.post<void>('/auth/logout', { refresh_token }),
  me: () => client.get<User>('/auth/me'),
  // Chat / run
  chat: (b: ChatRequest) => client.post<ChatAccepted>('/chat', b),
  streamTicket: (runId: string) => client.post<StreamTicket>(`/chat/${runId}/stream-ticket`),
  cancel: (runId: string) => client.post<CancelResponse>(`/chat/${runId}/cancel`),
  // Sessions
  sessions: (limit = 20, offset = 0) => client.get<SessionList>(`/sessions?limit=${limit}&offset=${offset}`),
  session: (id: string) => client.get<SessionDetail>(`/sessions/${id}`),
  // Groups
  groups: (limit = 20, offset = 0) => client.get<GroupList>(`/groups?limit=${limit}&offset=${offset}`),
  group: (id: string) => client.get<Group>(`/groups/${id}`),
  createGroup: (b: CreateGroupRequest) => client.post<Group>('/groups', b),
  groupPreferences: (id: string) => client.get<GroupPreferences>(`/groups/${id}/preferences`),
  groupPlans: (id: string) => client.get<PlanList>(`/groups/${id}/plans`),
  // Plans
  plan: (id: string) => client.get<Plan>(`/plans/${id}`),
  planMap: (id: string) => client.get<PlanMap>(`/plans/${id}/map`),
  planCalendar: (id: string) => client.get<PlanCalendar>(`/plans/${id}/calendar`),
  acceptPlan: (id: string) => client.post<Plan>(`/plans/${id}/accept`),
  rejectPlan: (id: string, reason?: string) => client.post<Plan>(`/plans/${id}/reject`, { reason }),
  modifyPlan: (id: string, b: ModifyRequest) => client.post<ModifyAccepted>(`/plans/${id}/modify`, b),
}
