import axios from 'axios';
import type {
  AuthTokens,
  User,
  Facility,
  Claim,
  Patient,
  Ticket,
  Credential,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach Bearer token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 with token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken,
        });
        const newToken = data.access_token;
        localStorage.setItem('access_token', newToken);
        if (data.refresh_token) {
          localStorage.setItem('refresh_token', data.refresh_token);
        }
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  login: async (email: string, password: string): Promise<AuthTokens> => {
    const { data } = await api.post('/auth/login', { email, password });
    return data;
  },
  me: async (): Promise<User> => {
    const { data } = await api.get('/auth/me');
    return data;
  },
  refresh: async (refreshToken: string): Promise<AuthTokens> => {
    const { data } = await api.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return data;
  },
};

// Facilities
export const facilitiesApi = {
  list: async (): Promise<Facility[]> => {
    const { data } = await api.get('/facilities/');
    return data;
  },
  get: async (id: string): Promise<Facility> => {
    const { data } = await api.get(`/facilities/${id}`);
    return data;
  },
};

// Claims
export const claimsApi = {
  list: async (params?: {
    status?: string;
    facility_id?: string;
  }): Promise<Claim[]> => {
    const { data } = await api.get('/claims/', { params });
    return data;
  },
  get: async (id: string): Promise<Claim> => {
    const { data } = await api.get(`/claims/${id}`);
    return data;
  },
  create: async (claim: Partial<Claim>): Promise<Claim> => {
    const { data } = await api.post('/claims/', claim);
    return data;
  },
  update: async (id: string, claim: Partial<Claim>): Promise<Claim> => {
    const { data } = await api.patch(`/claims/${id}`, claim);
    return data;
  },
  transition: async (
    id: string,
    newStatus: string,
    notes?: string
  ): Promise<Claim> => {
    const { data } = await api.post(`/claims/${id}/transition`, {
      status: newStatus,
      notes,
    });
    return data;
  },
};

// Patients
export const patientsApi = {
  list: async (params?: { search?: string }): Promise<Patient[]> => {
    const { data } = await api.get('/patients/', { params });
    return data;
  },
};

// Tickets
export const ticketsApi = {
  list: async (params?: { status?: string }): Promise<Ticket[]> => {
    const { data } = await api.get('/tickets/', { params });
    return data;
  },
};

// Credentials
export const credentialsApi = {
  list: async (): Promise<Credential[]> => {
    const { data } = await api.get('/credentials/');
    return data;
  },
  expiring: async (days: number = 90): Promise<Credential[]> => {
    const { data } = await api.get('/credentials/expiring', {
      params: { days },
    });
    return data;
  },
};

// Health
export const healthApi = {
  check: async (): Promise<{ status: string }> => {
    const { data } = await api.get('/health');
    return data;
  },
};

export default api;
