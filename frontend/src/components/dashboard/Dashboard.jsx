import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react';
import RoadmapGraph from '../roadmap/RoadmapGraph';
import ProgressPanel from './ProgressPanel';
import FilterPanel from './FilterPanel';
import { fetchLearningPath, scanRepositories } from '../../store/roadmapSlice';
import toast from 'react-hot-toast';

const Dashboard = () => {
  const dispatch = useDispatch();
  const { 
    learningPath, 
    repositories, 
    isLoading, 
    error, 
    lastScanTime 
  } = useSelector((state) => state.roadmap);
  
  const [activeTab, setActiveTab] = useState('roadmap');
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
    // Load existing learning path on component mount
    dispatch(fetchLearningPath());
  }, [dispatch]);

  const handleScanRepositories = async () => {
    setIsScanning(true);
    try {
      await dispatch(scanRepositories()).unwrap();
      toast.success('Repositories scanned successfully!');
    } catch (error) {
      toast.error('Failed to scan repositories: ' + error.message);
    } finally {
      setIsScanning(false);
    }
  };

  const handleRefreshPath = async () => {
    try {
      await dispatch(fetchLearningPath()).unwrap();
      toast.success('Learning path refreshed!');
    } catch (error) {
      toast.error('Failed to refresh learning path');
    }
  };

  if (isLoading && !learningPath) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading learning path...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Learning Dashboard</h2>
          <p className="text-gray-600 mt-1">
            {lastScanTime 
              ? `Last scan: ${new Date(lastScanTime).toLocaleString()}`
              : 'No repositories scanned yet'
            }
          </p>
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={handleScanRepositories}
            disabled={isScanning}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isScanning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            <span>{isScanning ? 'Scanning...' : 'Scan Repositories'}</span>
          </button>
          
          <button
            onClick={handleRefreshPath}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <p className="text-red-800 font-medium">Error</p>
          </div>
          <p className="text-red-700 mt-1">{error}</p>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'roadmap', label: 'Interactive Roadmap' },
            { id: 'progress', label: 'Progress Tracking' },
            { id: 'filters', label: 'Filters & Search' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'roadmap' && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            {learningPath && learningPath.nodes && learningPath.nodes.length > 0 ? (
              <RoadmapGraph 
                learningPath={learningPath}
                repositories={repositories}
              />
            ) : (
              <div className="text-center py-12">
                <Map className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  No Learning Path Generated
                </h3>
                <p className="text-gray-600 mb-4">
                  Scan your repositories to generate an AI-powered learning path
                </p>
                <button
                  onClick={handleScanRepositories}
                  disabled={isScanning}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {isScanning ? 'Scanning...' : 'Start Scanning'}
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'progress' && (
          <ProgressPanel learningPath={learningPath} />
        )}

        {activeTab === 'filters' && (
          <FilterPanel repositories={repositories} />
        )}
      </div>

      {/* Statistics Cards */}
      {learningPath && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-medium text-gray-500">Total Repositories</h3>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {learningPath.nodes?.length || 0}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-medium text-gray-500">Completion</h3>
            <p className="text-2xl font-bold text-green-600 mt-2">
              {Math.round(learningPath.completion_percentage || 0)}%
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-medium text-gray-500">Estimated Hours</h3>
            <p className="text-2xl font-bold text-blue-600 mt-2">
              {learningPath.total_estimated_hours || 0}h
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-medium text-gray-500">Status</h3>
            <p className="text-2xl font-bold text-purple-600 mt-2 capitalize">
              {learningPath.status || 'Draft'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;