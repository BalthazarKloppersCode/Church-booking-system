import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api';

export function useAdmin() {
  const [admin, setAdmin] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      navigate('/admin/login');
      return;
    }
    api
      .adminMe()
      .then(setAdmin)
      .catch(() => {
        localStorage.removeItem('admin_token');
        navigate('/admin/login');
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  return { admin, loading };
}

export function logoutAdmin(navigate) {
  localStorage.removeItem('admin_token');
  navigate('/admin/login');
}
