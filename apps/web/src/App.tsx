import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Claims from './pages/Claims';
import ClaimDetail from './pages/ClaimDetail';
import Facilities from './pages/Facilities';
import Tickets from './pages/Tickets';
import Credentials from './pages/Credentials';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/claims" element={<Claims />} />
            <Route path="/claims/:id" element={<ClaimDetail />} />
            <Route path="/facilities" element={<Facilities />} />
            <Route path="/tickets" element={<Tickets />} />
            <Route path="/credentials" element={<Credentials />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
