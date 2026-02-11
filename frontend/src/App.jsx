import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { Toaster } from 'react-hot-toast';
import { store } from './store';
import Header from './components/common/Header';
import Dashboard from './components/dashboard/Dashboard';
import ErrorBoundary from './components/common/ErrorBoundary';
import './styles/globals.css';

function App() {
  return (
    <Provider store={store}>
      <ErrorBoundary>
        <Router>
          <div className="min-h-screen bg-gray-50">
            <Header />
            <main className="container mx-auto px-4 py-8">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/roadmap" element={<Dashboard />} />
                <Route path="/progress" element={<Dashboard />} />
                <Route path="/export" element={<Dashboard />} />
              </Routes>
            </main>
            <Toaster 
              position="top-right"
              toastOptions={{
                duration: 4000,
                style: {
                  background: '#363636',
                  color: '#fff',
                },
              }}
            />
          </div>
        </Router>
      </ErrorBoundary>
    </Provider>
  );
}

export default App;